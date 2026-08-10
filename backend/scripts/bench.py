"""Endpoint latency benchmark against an in-process app (fresh seeded DB).

Measures median and p90 over N requests per endpoint. Used to validate
performance work with real numbers — see docs/PERFORMANCE.md.

Usage:
    python scripts/bench.py [--n 30]
"""

import argparse
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ENDPOINTS = [
    "/api/feed",
    "/api/feed/movers",
    "/api/questions",
    "/api/questions/1",
    "/api/questions/1/history",
    "/api/brief?count=5",
    "/api/leaderboard",
    "/api/leaderboard/calibration",
    "/api/leaderboard/predictions",
    "/api/stats",
    "/api/agents/leaderboard",
    "/api/cards/1.svg",
]


def run_bench(client, n: int) -> list[tuple[str, float, float]]:
    rows = []
    for endpoint in ENDPOINTS:
        client.get(endpoint)  # warm (caches, first-touch imports)
        samples = []
        for _ in range(n):
            start = time.perf_counter()
            response = client.get(endpoint)
            samples.append((time.perf_counter() - start) * 1000)
            response.raise_for_status()
        samples.sort()
        rows.append((endpoint, statistics.median(samples), samples[int(0.9 * len(samples))]))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=30)
    args = parser.parse_args()

    tmpdir = tempfile.mkdtemp(prefix="vanta-bench-")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmpdir}/bench.db"
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    get_settings.cache_clear()
    with TestClient(app) as client:
        rows = run_bench(client, args.n)
    print(f"{'endpoint':42s} {'median':>9s} {'p90':>9s}")
    for endpoint, median, p90 in rows:
        print(f"{endpoint:42s} {median:8.2f}ms {p90:8.2f}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
