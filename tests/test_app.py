from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_unhealthy_when_forced(monkeypatch):
    monkeypatch.setenv("FORCE_UNHEALTHY", "1")
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "unhealthy"
