import pytest
from fastapi.testclient import TestClient

from app.main import app  # DB binding happens in conftest.py


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_meta_identity(client):
    body = client.get("/api/meta").json()
    assert body["name"] == "vanta"
    assert body["version"]
    assert body["source"].startswith("https://github.com/")
