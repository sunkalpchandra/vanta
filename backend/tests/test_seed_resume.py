"""Regression: a crash between the question commit and the forecast commit
used to leave a seeded question permanently forecast-less — the resumability
the seeding docstring promises."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.data import SEED_QUESTIONS
from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import AgentReport, Forecast, Question
from app.seed import seed_if_empty


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_seed_completes_partially_seeded_questions(client):
    text = SEED_QUESTIONS[2]["question"]
    with SessionLocal() as db:
        question = db.scalar(select(Question).where(Question.question == text))
        assert question is not None and not question.resolved
        # Simulate the crash window: question row exists, no forecast state.
        db.query(Forecast).filter(Forecast.question_id == question.id).delete()
        db.query(AgentReport).filter(AgentReport.question_id == question.id).delete()
        db.commit()

        assert seed_if_empty(db) is True  # detected and finished the job

        n_forecasts = db.query(Forecast).filter(Forecast.question_id == question.id).count()
        n_reports = db.query(AgentReport).filter(AgentReport.question_id == question.id).count()
    assert n_forecasts >= 31  # fresh forecast + 30-day backfill
    assert n_reports == 7


def test_seed_noop_when_complete(client):
    with SessionLocal() as db:
        assert seed_if_empty(db) is False
