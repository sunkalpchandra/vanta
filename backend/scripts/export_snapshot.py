"""Export a static snapshot of the vanta API for the GitHub Pages demo.

Boots the app against a throwaway SQLite database (fresh deterministic seed),
walks the read API, and writes JSON + SVG assets into the frontend's public/
directory. The static frontend build (NEXT_PUBLIC_STATIC_MODE=1) reads these
files instead of a live backend.

Usage:
    python scripts/export_snapshot.py --out ../frontend/public
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


def export_snapshot(client, out_dir: Path) -> list[str]:
    """Dump the read API to out_dir. Returns the list of files written."""
    data = out_dir / "data"
    (data / "questions").mkdir(parents=True, exist_ok=True)
    (data / "history").mkdir(parents=True, exist_ok=True)
    (data / "market-history").mkdir(parents=True, exist_ok=True)
    (data / "sensitivity").mkdir(parents=True, exist_ok=True)
    (data / "related").mkdir(parents=True, exist_ok=True)
    (data / "changes").mkdir(parents=True, exist_ok=True)
    (data / "agent-records").mkdir(parents=True, exist_ok=True)
    (data / "agent-calibration").mkdir(parents=True, exist_ok=True)
    (out_dir / "cards").mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    def dump(path: Path, payload) -> None:
        path.write_text(json.dumps(payload, indent=1))
        written.append(str(path.relative_to(out_dir)))

    def fetch(endpoint: str):
        response = client.get(endpoint)
        response.raise_for_status()  # never bake an error body into the snapshot
        return response.json()

    top_level = {
        "feed.json": "/api/feed",
        "questions.json": "/api/questions",
        "brief.json": "/api/brief",
        "leaderboard.json": "/api/leaderboard",
        "calibration.json": "/api/leaderboard/calibration",
        "predictions.json": "/api/leaderboard/predictions",
        "agents.json": "/api/agents/leaderboard",
        "movers.json": "/api/feed/movers",
        "backtest.json": "/api/quant/backtest",
        "sparklines.json": "/api/feed/sparklines",
        "alerts.json": "/api/alerts",
        "stats.json": "/api/stats",
        "categories.json": "/api/categories",
    }
    for filename, endpoint in top_level.items():
        response = client.get(endpoint)
        response.raise_for_status()
        dump(data / filename, response.json())

    questions = client.get("/api/questions").json()
    for question in questions:
        qid = question["id"]
        dump(data / "questions" / f"{qid}.json", fetch(f"/api/questions/{qid}"))
        dump(data / "history" / f"{qid}.json", fetch(f"/api/questions/{qid}/history"))
        dump(
            data / "market-history" / f"{qid}.json",
            fetch(f"/api/questions/{qid}/market-history"),
        )
        dump(
            data / "sensitivity" / f"{qid}.json",
            fetch(f"/api/questions/{qid}/sensitivity"),
        )
        dump(data / "related" / f"{qid}.json", fetch(f"/api/questions/{qid}/related"))
        dump(data / "changes" / f"{qid}.json", fetch(f"/api/questions/{qid}/changes"))
        card = client.get(f"/api/cards/{qid}.svg")
        card.raise_for_status()
        card_path = out_dir / "cards" / f"{qid}.svg"
        card_path.write_text(card.text)
        written.append(str(card_path.relative_to(out_dir)))

    for agent_name in ["research", "quant", "market", "sentiment", "historian", "synthesis"]:
        response = client.get(f"/api/agents/{agent_name}/records")
        response.raise_for_status()
        dump(data / "agent-records" / f"{agent_name}.json", response.json())
        calibration = client.get(f"/api/agents/{agent_name}/calibration")
        calibration.raise_for_status()
        dump(data / "agent-calibration" / f"{agent_name}.json", calibration.json())

    rss = client.get("/api/brief/rss")
    rss.raise_for_status()
    (out_dir / "brief.xml").write_text(rss.text)
    written.append("brief.xml")

    csv_response = client.get("/api/leaderboard/predictions.csv")
    csv_response.raise_for_status()
    (out_dir / "track-record.csv").write_text(csv_response.text)
    written.append("track-record.csv")

    # Real-market backtest scorecards: bake honestly — a 404 (no rows yet)
    # becomes an explicit unavailable sentinel, never a fake result.
    for horizon in (7, 30):
        response = client.get(f"/api/backtest/real?horizon={horizon}")
        payload = (
            {"available": True, **response.json()}
            if response.status_code == 200
            else {"available": False}
        )
        dump(data / f"backtest-real-{horizon}.json", payload)

    # Markets sample for the play-money trading surface. The fresh bake DB has
    # no synced venue events (and the markets router may not be mounted at all),
    # so a 404 or an empty answer bakes an honest sentinel — never a crash and
    # never a fabricated market list.
    def fetch_markets(endpoint: str) -> tuple[list, int] | None:
        response = client.get(endpoint)
        if response.status_code == 404:
            return None
        response.raise_for_status()  # non-404 errors still fail the bake
        payload = response.json()
        if isinstance(payload, list):
            return payload, len(payload)
        items = payload.get("items", [])
        return items, int(payload.get("total", len(items)))

    active_items, total_active = fetch_markets("/api/markets?status=active&sort=volume&limit=100") or ([], 0)
    settled_items, total_settled = fetch_markets("/api/markets?status=settled&limit=100") or ([], 0)
    if not active_items and not settled_items:
        markets_sample = {
            "active": [],
            "settled": [],
            "sampled": True,
            "note": "no synced market events in the bake database",
        }
    else:
        markets_sample = {
            "active": active_items,
            "settled": settled_items,
            "total_active": total_active,
            "total_settled": total_settled,
            "sampled": True,
        }
    dump(data / "markets-sample.json", markets_sample)

    # Trader leaderboard — empty on a fresh bake DB (nobody has traded there),
    # which the UI renders as an honest "no traders yet" state.
    traders_resp = client.get("/api/markets/traders")
    dump(
        data / "traders.json",
        traders_resp.json() if traders_resp.status_code == 200 else {"traders": []},
    )

    # Market-surface stats + biggest movers.
    stats_resp = client.get("/api/market-stats")
    dump(data / "market-stats.json", stats_resp.json() if stats_resp.status_code == 200 else None)
    movers_resp = client.get("/api/market-stats/movers?window_hours=24&limit=20")
    dump(data / "market-movers.json", movers_resp.json() if movers_resp.status_code == 200 else [])

    # Public activity tape — recent trades across all traders (bots included).
    activity_resp = client.get("/api/activity/trades?limit=30")
    dump(
        data / "activity.json",
        activity_resp.json() if activity_resp.status_code == 200 else {"trades": []},
    )

    # Price-history series for every sampled market, so the detail page charts
    # render in the static demo.
    (data / "market-price").mkdir(parents=True, exist_ok=True)
    sampled_ids = {m["id"] for m in active_items} | {m["id"] for m in settled_items}
    for event_id in sampled_ids:
        resp = client.get(f"/api/markets/{event_id}/history")
        dump(data / "market-price" / f"{event_id}.json", resp.json() if resp.status_code == 200 else {"points": []})

    # vanta's forecast for each ACTIVE sampled market — the detail page's
    # "vanta's take" section, real in the static demo (deterministic pipeline).
    (data / "market-forecast").mkdir(parents=True, exist_ok=True)
    for m in active_items:
        resp = client.get(f"/api/markets/{m['id']}/forecast")
        dump(data / "market-forecast" / f"{m['id']}.json", resp.json() if resp.status_code == 200 else None)

    dump(
        data / "meta.json",
        {"mode": "static-demo", "questions": len(questions), "commit": os.environ.get("GIT_SHA")},
    )
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="output directory (frontend/public)")
    args = parser.parse_args()

    # Existing-DB passthrough: the Pages workflow's scheduled bake seeds and
    # syncs a workspace DB first, then exports against it by pre-setting
    # DATABASE_URL (that's how markets-sample.json gets real synced events).
    # Without one, fall back to a fresh throwaway DB so a local snapshot is
    # always a clean deterministic seed.
    if not os.environ.get("DATABASE_URL"):
        tmpdir = tempfile.mkdtemp(prefix="vanta-snapshot-")
        os.environ["DATABASE_URL"] = f"sqlite:///{tmpdir}/snapshot.db"

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import app

    get_settings.cache_clear()
    out_dir = Path(args.out).resolve()
    with TestClient(app) as client:
        written = export_snapshot(client, out_dir)
    print(f"wrote {len(written)} files to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
