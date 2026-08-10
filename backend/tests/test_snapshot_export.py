import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_tmpdir = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmpdir}/test_snapshot.db")

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from export_snapshot import export_snapshot  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def snapshot_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("snapshot")
    with TestClient(app) as client:
        export_snapshot(client, out)
    return out


def test_snapshot_top_level_files(snapshot_dir):
    for name in ["feed", "questions", "brief", "leaderboard", "calibration", "stats", "categories", "meta"]:
        path = snapshot_dir / "data" / f"{name}.json"
        assert path.exists(), name
        json.loads(path.read_text())


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
