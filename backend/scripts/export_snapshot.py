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
    (out_dir / "cards").mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    def dump(path: Path, payload) -> None:
        path.write_text(json.dumps(payload, indent=1))
        written.append(str(path.relative_to(out_dir)))

    top_level = {
        "feed.json": "/api/feed",
        "questions.json": "/api/questions",
        "brief.json": "/api/brief",
        "leaderboard.json": "/api/leaderboard",
        "calibration.json": "/api/leaderboard/calibration",
        "predictions.json": "/api/leaderboard/predictions",
        "agents.json": "/api/agents/leaderboard",
        "movers.json": "/api/feed/movers",
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
        dump(data / "questions" / f"{qid}.json", client.get(f"/api/questions/{qid}").json())
        dump(data / "history" / f"{qid}.json", client.get(f"/api/questions/{qid}/history").json())
        card = client.get(f"/api/cards/{qid}.svg")
        card.raise_for_status()
        card_path = out_dir / "cards" / f"{qid}.svg"
        card_path.write_text(card.text)
        written.append(str(card_path.relative_to(out_dir)))

    dump(data / "meta.json", {"mode": "static-demo", "questions": len(questions)})
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="output directory (frontend/public)")
    args = parser.parse_args()

    # Fresh throwaway DB so every snapshot is a clean deterministic seed.
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
