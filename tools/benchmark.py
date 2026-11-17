"""Execute both 5-minute measurements against the real Compose gateway."""

import csv
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def main():
    env_path = ROOT / ".env"
    original = env_path.read_text(encoding="utf-8")
    report = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "users": 50,
        "duration_s_each": 300,
        "spawn_rate": 50,
        "wait_s": [0.2, 1.0],
        "common_fraction_target": 0.3,
        "provider": "mock",
        "mock_delay_s": 0.15,
        "rate_limit_per_min": 100000,
        "host": platform.platform(),
        "runs": {},
    }
    try:
        for mode in ("no_cache", "with_cache"):
            config = (ROOT / ".env.example").read_text()
            config = config.replace("RATE_LIMIT_PER_MIN=30", "RATE_LIMIT_PER_MIN=100000")
            config = config.replace("CACHE_ENABLED=true", f"CACHE_ENABLED={str(mode == 'with_cache').lower()}")
            env_path.write_text(config, encoding="utf-8")
            run("docker", "compose", "exec", "-T", "redis", "redis-cli", "FLUSHDB")
            run("docker", "compose", "up", "-d", "--wait", "--force-recreate", "gateway")
            with httpx.Client() as client:
                assert client.get("http://localhost:8000/health").status_code == 200
            prefix = ROOT / "results" / mode
            env = {**os.environ, "LOAD_COUNTS_FILE": str(prefix) + "_counts.json"}
            started = time.perf_counter()
            with open(str(prefix) + "_locust.log", "w", encoding="utf-8") as log:
                run(
                    sys.executable,
                    "-m",
                    "locust",
                    "-f",
                    "loadtest/locustfile.py",
                    "--headless",
                    "-u",
                    "50",
                    "-r",
                    "50",
                    "-t",
                    "300s",
                    "--stop-timeout",
                    "10",
                    "--host",
                    "http://localhost:8000",
                    "--csv",
                    str(prefix),
                    "--csv-full-history",
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            elapsed = time.perf_counter() - started
            rows = list(csv.DictReader(Path(str(prefix) + "_stats.csv").open(encoding="utf-8")))
            row = next(row for row in rows if row["Name"] == "Aggregated")
            counts = json.loads(Path(str(prefix) + "_counts.json").read_text())
            health = httpx.get("http://localhost:8000/health").json()
            (ROOT / f"results/{mode}_metrics.txt").write_text(
                httpx.get("http://localhost:8000/metrics").text, encoding="utf-8"
            )
            with (ROOT / f"results/{mode}_gateway.log").open("w", encoding="utf-8") as log:
                run("docker", "compose", "logs", "--no-color", "gateway", stdout=log)
            report["runs"][mode] = {
                "p50_ms": float(row["50%"]),
                "p95_ms": float(row["95%"]),
                "throughput_rps": float(row["Requests/s"]),
                "requests": int(row["Request Count"]),
                "failures": int(row["Failure Count"]),
                "cache_hit_percent": round(100 * counts["hits"] / counts["responses"], 3),
                "elapsed_s": round(elapsed, 2),
                "counts": counts,
                "health": health,
            }
            (ROOT / "results/benchmark.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(mode, report["runs"][mode], flush=True)
    finally:
        env_path.write_text(original, encoding="utf-8")
        run("docker", "compose", "up", "-d", "--wait", "--force-recreate", "gateway")


if __name__ == "__main__":
    main()
