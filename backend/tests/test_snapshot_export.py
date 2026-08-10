import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from export_snapshot import export_snapshot  # noqa: E402

from app.main import app  # noqa: E402  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def snapshot_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("snapshot")
    with TestClient(app) as client:
        export_snapshot(client, out)
    return out


# Lockstep guard: every snapshot name frontend/lib/data.ts reads must exist.
# When adding a getter there, extend this list AND export_snapshot.py.
DATA_TS_SNAPSHOT_NAMES = [
    "feed",
    "questions",
    "brief",
    "leaderboard",
    "calibration",
    "predictions",
    "stats",
    "categories",
    "movers",
    "agents",
    "backtest",
    "meta",
]


def test_snapshot_top_level_files(snapshot_dir):
    for name in DATA_TS_SNAPSHOT_NAMES:
        path = snapshot_dir / "data" / f"{name}.json"
        assert path.exists(), name
        json.loads(path.read_text())


def test_snapshot_brief_xml(snapshot_dir):
    rss = (snapshot_dir / "brief.xml").read_text()
    assert rss.startswith("<?xml") and "vanta Morning Brief" in rss


def test_snapshot_per_question_files(snapshot_dir):
    questions = json.loads((snapshot_dir / "data" / "questions.json").read_text())
    assert len(questions) >= 10
    for q in questions:
        assert (snapshot_dir / "data" / "questions" / f"{q['id']}.json").exists()
        assert (snapshot_dir / "data" / "history" / f"{q['id']}.json").exists()
        assert (snapshot_dir / "cards" / f"{q['id']}.svg").exists()


def test_snapshot_feed_is_nonempty_and_consistent(snapshot_dir):
    feed = json.loads((snapshot_dir / "data" / "feed.json").read_text())
    question_ids = {q["id"] for q in json.loads((snapshot_dir / "data" / "questions.json").read_text())}
    assert feed
    assert all(card["question_id"] in question_ids for card in feed)
