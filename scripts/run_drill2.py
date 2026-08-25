import os
import subprocess
import time

def run():
    print("--- Starting Drill 2 Sequence ---")
    for p in ["reports/drill-2-withdr.jsonl", "reports/health-events.jsonl", "reports/failover-events.jsonl", "reports/runbook-run.jsonl"]:
        if os.path.exists(p):
            os.remove(p)

    ingest_p = subprocess.Popen([".venv/bin/python3", "state/ingest.py", "--region", "a", "--rate", "1.0", "--duration", "120"])
    replicate_p = subprocess.Popen([".venv/bin/python3", "state/replicate.py", "--every", "5", "--duration", "120", "--backend", "fs"])

    print("Waiting 5s for first replication cycle...")
    time.sleep(5)

    traffic_p = subprocess.Popen([".venv/bin/python3", "loadgen/traffic.py", "--duration", "90", "--rps", "2", "--out", "reports/drill-2-withdr.jsonl"])
    health_p = subprocess.Popen([".venv/bin/python3", "dr/health_checker.py", "--interval", "5", "--threshold", "3", "--duration", "90", "--out", "reports/health-events.jsonl"])

    print("Waiting 12s before chaos kill...")
    time.sleep(12)

    print("Executing chaos kill on Region A...")
    subprocess.run([".venv/bin/python3", "chaos/kill_region.py", "--region", "a", "--mode", "netblock", "--mock"], check=True)

    print("Waiting 15s for health checker to detect UNHEALTHY...")
    time.sleep(15)

    print("Executing Runbook failover to Region B...")
    subprocess.run([".venv/bin/python3", "dr/runbook.py", "--primary", "a", "--target", "b", "--backend", "fs", "--auto"], check=True)

    print("Waiting 20s for remaining traffic to be served by Region B...")
    time.sleep(20)

    try:
        ingest_p.terminate()
        replicate_p.terminate()
        traffic_p.terminate()
        health_p.terminate()
    except Exception:
        pass

    print("Drill 2 execution finished!")

if __name__ == "__main__":
    run()
