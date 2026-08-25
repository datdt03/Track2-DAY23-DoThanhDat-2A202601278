"""BƯỚC 3a — SINH VIÊN VIẾT. Health checker cho 2 region.

Yêu cầu (đọc §4 "Kiến Trúc Health-Check-Based Failover" + §2 "DNS Failover"):
  1. Poll /readyz của CẢ HAI region mỗi `interval` giây (mặc định 5s).
     Dùng /readyz, KHÔNG dùng /healthz. /healthz chỉ nói "process còn sống" —
     region có process sống nhưng vector DB rỗng thì vẫn không serve được.
  2. Chỉ đổi trạng thái sau `threshold` lần fail LIÊN TIẾP (mặc định 3).
     Một lần fail không phải outage. Đây là chống flapping (§4 Anti-Patterns).
  3. Ghi 1 dòng JSONL MỖI LẦN ĐỔI TRẠNG THÁI (không ghi mỗi lần poll — log sẽ ngập).
     Dòng bắt buộc có: ts, region, to (HEALTHY|UNHEALTHY), reason,
     interval_s, threshold. Thiếu interval_s/threshold thì tools/measure_rto.py
     không tính được detect floor -> mất điểm.

Chạy:  python dr/health_checker.py --interval 5 --threshold 3 --duration 300 \
              --out reports/health-events.jsonl
"""
import argparse
import json
import pathlib
import time

import httpx

URL = {"a": "http://127.0.0.1:8001", "b": "http://127.0.0.1:8002"}


def probe(region: str, timeout: float) -> tuple[bool, str]:
    """Trả về (ready, reason). Timeout PHẢI có — netblock làm request treo mãi."""
    url = f"{URL[region]}/readyz"
    try:
        r = httpx.get(url, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            if data.get("ready"):
                return True, "ok"
            return False, f"not_ready:{','.join(data.get('reasons', []))}"
        return False, f"status_{r.status_code}"
    except Exception as e:
        return False, str(e)


def run(interval: float, timeout: float, threshold: int, duration: float, out: pathlib.Path):
    """Vòng lặp poll + phát hiện transition + ghi JSONL."""
    out.parent.mkdir(parents=True, exist_ok=True)

    current_state = {"a": "HEALTHY", "b": "HEALTHY"}
    consecutive_fails = {"a": 0, "b": 0}
    consecutive_successes = {"a": 0, "b": 0}

    start_time = time.time()

    while time.time() - start_time < duration:
        t_cycle_start = time.time()
        for region in ["a", "b"]:
            is_ready, reason = probe(region, timeout)
            if is_ready:
                consecutive_fails[region] = 0
                consecutive_successes[region] += 1
                if current_state[region] == "UNHEALTHY" and consecutive_successes[region] >= 1:
                    prev = current_state[region]
                    current_state[region] = "HEALTHY"
                    now = time.time()
                    event = {
                        "event": "state_change",
                        "ts": now,
                        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                        "region": region,
                        "from": prev,
                        "to": "HEALTHY",
                        "reason": reason,
                        "interval_s": interval,
                        "threshold": threshold,
                        "consecutive_fails": consecutive_fails[region]
                    }
                    with open(out, "a") as f:
                        f.write(json.dumps(event) + "\n")
                    print(f"HEALTH {json.dumps(event)}")
            else:
                consecutive_successes[region] = 0
                consecutive_fails[region] += 1
                if current_state[region] == "HEALTHY" and consecutive_fails[region] >= threshold:
                    prev = current_state[region]
                    current_state[region] = "UNHEALTHY"
                    now = time.time()
                    event = {
                        "event": "state_change",
                        "ts": now,
                        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                        "region": region,
                        "from": prev,
                        "to": "UNHEALTHY",
                        "reason": reason,
                        "interval_s": interval,
                        "threshold": threshold,
                        "consecutive_fails": consecutive_fails[region]
                    }
                    with open(out, "a") as f:
                        f.write(json.dumps(event) + "\n")
                    print(f"HEALTH {json.dumps(event)}")

        elapsed = time.time() - t_cycle_start
        to_sleep = max(0.0, interval - elapsed)
        time.sleep(to_sleep)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--interval", type=float, default=5.0)
    p.add_argument("--timeout", type=float, default=2.0)
    p.add_argument("--threshold", type=int, default=3)
    p.add_argument("--duration", type=float, default=300)
    p.add_argument("--out", default="reports/health-events.jsonl")
    a = p.parse_args()
    run(a.interval, a.timeout, a.threshold, a.duration, pathlib.Path(a.out))
