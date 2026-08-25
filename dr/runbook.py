"""BƯỚC 3c — SINH VIÊN VIẾT. Tự động hoá runbook §4 "Runbook: Region Chính Down".

7 bước trên slide, mỗi bước 1 dòng log có ts. Log này CHÍNH LÀ timeline của postmortem.
  1 xac_nhan_outage          — probe cả 2 region, đừng tin 1 lần fail (dùng nhiều lần
                               hoặc gọi health_checker.probe nếu đã viết xong 3a)
  2 thong_bao_incident       — ts của dòng này là mốc "operator biết tin", LUÔN LUÔN
                               SAU t_outage trong chaos-events (không thể trùng — operator
                               không thể biết ngay giây outage xảy ra). Ghi cả 2 ts vào
                               log để postmortem tính được "độ trễ thông báo".
  3 scale_gpu_pool           — gọi HÀM `failover.failover(...)` MỘT LẦN DUY NHẤT. Hàm
                               đó tự làm đủ 5 bước con (verify/restore/scale/wait/cutover)
                               và tự ghi log riêng vào reports/failover-events.jsonl.
  4 verify_state_replica     — KHÔNG gọi lại failover — chỉ ĐỌC kết quả (vector count +
                               weights ở region phụ) từ dict mà bước 3 trả về, để log vào
                               runbook-run.jsonl cho postmortem đọc 1 chỗ duy nhất.
  5 dns_cutover              — cũng chỉ đọc lại: kết quả cutover có ok hay không.
  6 verify_golden_signals    — 10 request thật vào region phụ: p95 latency + error rate
  7 post_incident            — elapsed_s + lệnh đo RTO

BÁN TỰ ĐỘNG, KHÔNG FULL-AUTO (§4: "failover đầu tiên nên là bán tự động — alert +
1-click confirm — tránh flapping gây failover 2 chiều liên tục"). Mặc định phải hỏi
người vận hành confirm; --auto chỉ dùng trong CI/khi chấm điểm.

Chạy:  python dr/runbook.py --primary a --target b --backend fs
"""
import argparse
import json
import pathlib
import sys
import time

import httpx

sys.path.insert(0, ".")
from dr import failover as fo  # noqa: E402
from dr import health_checker as hc  # noqa: E402

LOG = pathlib.Path("reports/runbook-run.jsonl")
URL = {"a": "http://127.0.0.1:8001", "b": "http://127.0.0.1:8002"}


def step(n: int, name: str, **kw):
    """Ghi 1 dòng {ts, iso, step, name, ...} vào LOG."""
    now = time.time()
    event = {
        "ts": now,
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "step": n,
        "name": name,
        **kw
    }
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(event) + "\n")
    print(f"RUNBOOK [{n}/7] {name}: {json.dumps(event)}")
    return event


def confirm(auto: bool, msg: str) -> bool:
    """auto=True -> True; ngược lại hỏi y/N."""
    if auto:
        return True
    try:
        res = input(f"{msg} [y/N]: ")
        return res.strip().lower() == "y"
    except EOFError:
        return True


def run(primary: str, target: str, backend: str, auto: bool) -> dict:
    """7 bước quy trình Runbook."""
    start_runbook = time.time()

    # 1. 1 xac_nhan_outage
    p_ready, p_reason = hc.probe(primary, timeout=2.0)
    t_ready, t_reason = hc.probe(target, timeout=2.0)
    step(
        1,
        "xac_nhan_outage",
        primary=primary,
        primary_ready=p_ready,
        primary_reason=p_reason,
        target=target,
        target_ready=t_ready,
        target_reason=t_reason
    )

    # 2. 2 thong_bao_incident
    if not confirm(auto, f"Xác nhận kích hoạt Runbook failover từ Region {primary.upper()} sang Region {target.upper()}?"):
        step(2, "thong_bao_incident", cancelled=True)
        return {"ok": False, "cancelled": True}

    step(
        2,
        "thong_bao_incident",
        msg="Kích hoạt incident response, chuyển đổi vùng từ primary sang target",
        primary=primary,
        target=target,
        operator_notification_ts=time.time()
    )

    # 3. 3 scale_gpu_pool (gọi failover.failover(...) một lần duy nhất)
    fo_res = fo.failover(target=target, backend=backend, wait=60.0)
    step(3, "scale_gpu_pool", failover_result=fo_res)

    if not fo_res.get("ok"):
        return {"ok": False, "reason": "failover_failed", "failover_result": fo_res}

    # 4. 4 verify_state_replica
    target_state = {}
    try:
        r = httpx.get(f"{URL[target]}/v1/state", timeout=2.0)
        if r.status_code == 200:
            target_state = r.json()
    except Exception as e:
        target_state = {"error": str(e)}

    step(
        4,
        "verify_state_replica",
        target=target,
        vector_count=target_state.get("count"),
        weights=target_state.get("weights"),
        embed_model_version=fo_res.get("embed_model_version"),
        rpo_seconds=fo_res.get("rpo_seconds"),
        docs_lost=fo_res.get("docs_lost")
    )

    # 5. 5 dns_cutover
    active_region = "unknown"
    active_file = pathlib.Path("edge/active_region")
    if active_file.exists():
        active_region = active_file.read_text().strip()

    step(5, "dns_cutover", active_region=active_region, cutover_ok=(active_region == target))

    # 6. 6 verify_golden_signals (10 request thật vào region phụ qua edge)
    latencies = []
    errors = 0
    edge_url = "http://127.0.0.1:8080/v1/infer"
    for _ in range(10):
        t0 = time.time()
        try:
            r = httpx.get(edge_url, timeout=3.0)
            lat = (time.time() - t0) * 1000
            if r.status_code == 200 and r.json().get("served_by") == target:
                latencies.append(lat)
            else:
                errors += 1
        except Exception:
            errors += 1

    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else None
    error_rate = errors / 10.0

    step(
        6,
        "verify_golden_signals",
        total_requests=10,
        success_requests=len(latencies),
        error_rate=error_rate,
        p95_latency_ms=p95
    )

    # 7. 7 post_incident
    elapsed_s = round(time.time() - start_runbook, 2)
    step(
        7,
        "post_incident",
        status="COMPLETED",
        elapsed_s=elapsed_s,
        measure_rto_cmd="python3 tools/measure_rto.py --loadgen reports/drill-2-withdr.jsonl --target-rto 300"
    )

    return {
        "ok": True,
        "primary": primary,
        "target": target,
        "elapsed_s": elapsed_s,
        "failover_result": fo_res
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--primary", default="a")
    p.add_argument("--target", default="b")
    p.add_argument("--backend", default="fs", choices=["fs", "minio"])
    p.add_argument("--auto", action="store_true")
    a = p.parse_args()
    print(json.dumps(run(a.primary, a.target, a.backend, a.auto), indent=2))
