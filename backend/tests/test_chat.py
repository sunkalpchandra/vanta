import json

import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # context manager triggers lifespan (tables + seed)
        yield c


@pytest.fixture()
def gated_client():
    app.state.require_api_key = True
    with TestClient(app) as c:
        yield c
    app.state.require_api_key = None


def stream_chat(client, body):
    """POST /api/chat and parse the SSE stream into (event, payload) pairs.
    json.loads doubles as the every-payload-is-valid-JSON assertion."""
    events = []
    with client.stream("POST", "/api/chat", json=body) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        name = None
        for line in resp.iter_lines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                events.append((name, json.loads(line[len("data: ") :])))
    return events


def first(events, name):
    return next(data for n, data in events if n == name)


def test_chat_created_path_streams_full_debate_and_stores(client):
    before = {q["id"] for q in client.get("/api/questions").json()}
    body = {
        "question": "Will a crewed zeppelin circumnavigate Antarctica nonstop before 2032?",
        "category": "science",
        "horizon_days": 400,
    }
    events = stream_chat(client, body)
    names = [n for n, _ in events]
    assert names[0] == "status"
    assert names[-1] == "done"
    assert names.count("agent_report") >= 5
    assert "evidence" in names and "related" in names
    # The debate streams in exact pipeline order.
    agents = [d["agent"] for n, d in events if n == "agent_report"]
    assert agents == ["research", "quant", "market", "sentiment", "historian", "skeptic", "synthesis"]
    for _, report in [(n, d) for n, d in events if n == "agent_report"]:
        assert {"agent", "stance", "probability", "argument", "details"} <= set(report)

    status = first(events, "status")
    assert status["mode"] == "created"
    done = first(events, "done")
    qid = done["question_id"]
    assert qid == status["question_id"]
    assert qid not in before  # a new question row was created
    assert done["permalink"] == f"/questions/{qid}"
    assert 0 < done["forecast"]["probability"] < 1

    # The streamed run was persisted like an ask: forecast + all 7 reports.
    detail = client.get(f"/api/questions/{qid}").json()
    assert detail["latest_forecast"]["probability"] == done["forecast"]["probability"]
    assert len(detail["agent_reports"]) == 7


def test_chat_matched_path_replays_without_storing(client):
    target = client.get("/api/questions?resolved=false").json()[-1]  # oldest seeded, has evidence
    n_before = len(client.get("/api/questions").json())
    history_before = len(client.get(f"/api/questions/{target['id']}/history").json())

    events = stream_chat(client, {"question": target["question"]})
    status = first(events, "status")
    assert status["mode"] == "matched"
    assert status["question_id"] == target["id"]
    assert status["similarity"] >= 0.6
    assert [n for n, _ in events].count("agent_report") >= 5

    # Read-only replay: no new question row, no new forecast row.
    assert len(client.get("/api/questions").json()) == n_before
    assert len(client.get(f"/api/questions/{target['id']}/history").json()) == history_before

    evidence = first(events, "evidence")
    assert evidence, "seeded question must stream its evidence"
    assert {"source", "summary", "sentiment", "impact"} <= set(evidence[0])
    assert first(events, "done")["question_id"] == target["id"]


def test_chat_probability_matches_direct_pipeline_run(client):
    """Parity: the streamed numbers must be IDENTICAL to a direct run through
    the same context — the stream re-drives the pipeline, it must not fork it."""
    from app.agents.orchestrator import run_pipeline
    from app.db import SessionLocal
    from app.models import Question
    from app.service import build_context

    body = {
        "question": "Will the tidal kite array off Orkney export grid power continuously before 2030?",
        "category": "technology",
    }
    events = stream_chat(client, body)
    done = first(events, "done")
    with SessionLocal() as db:
        question = db.get(Question, done["question_id"])
        result = run_pipeline(build_context(db, question, question.evidence))
    assert done["forecast"]["probability"] == result.probability
    assert done["forecast"]["confidence"] == result.confidence
    assert done["forecast"]["risk_factors"] == result.risk_factors
    # The synthesis report in the stream carries the same final number.
    synthesis = next(d for n, d in events if n == "agent_report" and d["agent"] == "synthesis")
    assert round(synthesis["probability"], 4) == result.probability


def test_gated_chat_blocks_creation_but_not_matched_replay(gated_client):
    # Matched replay is read-only and stays open under API-key gating.
    target = gated_client.get("/api/questions?resolved=false").json()[-1]
    events = stream_chat(gated_client, {"question": target["question"]})
    assert first(events, "status")["mode"] == "matched"
    # Creating a new question through chat is a mutation: same 401 as ask.
    novel = {"question": "Will an uncredentialed chat request mint a brand new question row?"}
    assert gated_client.post("/api/chat", json=novel).status_code == 401
    key = gated_client.post("/api/users", json={"email": "chat-gate@vanta.test"}).json()["api_key"]
    with gated_client.stream("POST", "/api/chat", json=novel, headers={"X-API-Key": key}) as resp:
        assert resp.status_code == 200


def test_chat_validates_body(client):
    assert client.post("/api/chat", json={"question": "too short"}).status_code == 422
    assert client.post("/api/chat", json={"question": "x" * 501}).status_code == 422
