import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agents.historian import base_rate_for
from app.db import SessionLocal
from app.main import app  # DB binding happens in conftest.py
from app.models import Prediction
from app.service import learned_base_rate


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # ensures the seeded DB exists
        yield c


def test_learned_rate_tracks_observed_outcomes(client):
    with SessionLocal() as db:
        rows = db.execute(select(Prediction.outcome).where(Prediction.category == "finance")).all()
        observed = sum(o for (o,) in rows) / len(rows)
        static = base_rate_for("finance")
        learned = learned_base_rate(db, "finance")
        lo, hi = sorted((static, observed))
        assert lo <= learned <= hi  # a blend, never an extrapolation
        assert learned != static  # the record has weight


def test_learned_rate_falls_back_to_static_when_unresolved(client):
    with SessionLocal() as db:
        # No resolved predictions exist for a made-up category.
        assert learned_base_rate(db, "geopolitics-nonexistent") == base_rate_for(
            "geopolitics-nonexistent"
        )


def test_pseudo_count_damps_small_samples(client):
    with SessionLocal() as db:
        heavy = learned_base_rate(db, "finance", pseudo_count=1000.0)
        assert abs(heavy - base_rate_for("finance")) < 0.02  # huge prior ≈ static
