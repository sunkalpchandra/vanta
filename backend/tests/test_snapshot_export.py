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
    "sparklines",
    "alerts",
    "meta",
    "backtest-real-7",
    "backtest-real-30",
    "markets-sample",
    "traders",
    "activity",
    "market-stats",
    "market-movers",
]


def test_snapshot_top_level_files(snapshot_dir):
    for name in DATA_TS_SNAPSHOT_NAMES:
        path = snapshot_dir / "data" / f"{name}.json"
        assert path.exists(), name
        json.loads(path.read_text())


def test_snapshot_brief_xml(snapshot_dir):
    rss = (snapshot_dir / "brief.xml").read_text()
    assert rss.startswith("<?xml") and "vanta Morning Brief" in rss


def test_snapshot_related_and_agent_records(snapshot_dir):
    questions = json.loads((snapshot_dir / "data" / "questions.json").read_text())
    for q in questions:
        assert (snapshot_dir / "data" / "related" / f"{q['id']}.json").exists()
    for agent in ["research", "quant", "market", "sentiment", "historian", "synthesis"]:
        assert (snapshot_dir / "data" / "agent-records" / f"{agent}.json").exists()
        assert (snapshot_dir / "data" / "agent-calibration" / f"{agent}.json").exists()
    for q in questions:
        assert (snapshot_dir / "data" / "changes" / f"{q['id']}.json").exists()
    assert (snapshot_dir / "track-record.csv").read_text().startswith("question_id,")


def test_snapshot_per_question_files(snapshot_dir):
    questions = json.loads((snapshot_dir / "data" / "questions.json").read_text())
    assert len(questions) >= 10
    for q in questions:
        assert (snapshot_dir / "data" / "questions" / f"{q['id']}.json").exists()
        assert (snapshot_dir / "data" / "history" / f"{q['id']}.json").exists()
        assert (snapshot_dir / "data" / "market-history" / f"{q['id']}.json").exists()
        assert (snapshot_dir / "data" / "sensitivity" / f"{q['id']}.json").exists()
        assert (snapshot_dir / "cards" / f"{q['id']}.svg").exists()


def test_snapshot_feed_is_nonempty_and_consistent(snapshot_dir):
    feed = json.loads((snapshot_dir / "data" / "feed.json").read_text())
    question_ids = {q["id"] for q in json.loads((snapshot_dir / "data" / "questions.json").read_text())}
    assert feed
    assert all(card["question_id"] in question_ids for card in feed)


def test_snapshot_markets_sample_shape(snapshot_dir):
    sample = json.loads((snapshot_dir / "data" / "markets-sample.json").read_text())
    assert sample["sampled"] is True
    assert isinstance(sample["active"], list)
    assert isinstance(sample["settled"], list)
    # An empty bake (no synced venue events, or router not mounted yet) must
    # carry the honest sentinel note instead of pretending markets exist.
    if not sample["active"] and not sample["settled"]:
        assert sample["note"] == "no synced market events in the bake database"


def test_snapshot_meta_carries_commit_stamp(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_SHA", "deadbee")
    with TestClient(app) as client:
        export_snapshot(client, tmp_path)
    meta = json.loads((tmp_path / "data" / "meta.json").read_text())
    assert meta["commit"] == "deadbee"
    assert meta["mode"] == "static-demo"


def test_snapshot_per_market_dirs_present(snapshot_dir):
    """The per-market snapshot dirs the detail page reads (price series and
    vanta forecasts) must be baked whenever the sample has active markets —
    they're keyed by id, not in DATA_TS_SNAPSHOT_NAMES, so guard them here."""
    data = snapshot_dir / "data"
    sample = json.loads((data / "markets-sample.json").read_text())
    active = sample.get("active", [])
    if not active:
        return  # empty bake DB — nothing to key on
    assert (data / "market-price").is_dir()
    assert (data / "market-forecast").is_dir()
    for m in active:
        assert (data / "market-price" / f"{m['id']}.json").exists()
        assert (data / "market-forecast" / f"{m['id']}.json").exists()
