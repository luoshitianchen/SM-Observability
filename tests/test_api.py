"""SM Observability 领域测试：目标、模拟探测、历史、SLO、汇总与统计。"""

import pytest
from fastapi.testclient import TestClient

from app import base
from app.main import VERSION, app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(base, "internal_api_key", lambda: "TEST")
    base.reset_state()
    from app.main import _init as init_db
    init_db()
    with TestClient(app) as c:
        c.headers["X-Internal-Token"] = "TEST"
        yield c


def _target(client, name="fusion"):
    return client.post("/api/obs/targets", json={"name": name, "url": "http://127.0.0.1:8200/health", "owner": "SRE"}).json()["id"]


def test_health_and_version(client):
    r = client.get("/health", headers={"X-Request-Id": "suite-test"})
    assert r.status_code == 200
    assert r.json()["version"] == VERSION


def test_target_lifecycle(client):
    _target(client)
    assert client.post("/api/obs/targets", json={"name": "fusion", "url": "http://x"}).status_code == 409
    assert client.get("/api/obs/targets").json()["total"] == 1


def test_simulated_probe(client):
    target_id = _target(client)
    probe = client.post("/api/obs/probe", json={"target_id": target_id, "simulate": True}).json()
    assert probe["status"] == "up"
    assert probe["latency_ms"] > 0
    assert client.get(f"/api/obs/targets/{target_id}/history").json()["total"] == 1


def test_probe_missing_target(client):
    assert client.post("/api/obs/probe", json={"target_id": "nope"}).status_code == 404


def test_slo_and_summary(client):
    target_id = _target(client)
    client.post("/api/obs/probe", json={"target_id": target_id, "simulate": True})
    slo = client.post("/api/obs/slos", json={"name": "fusion-slo", "target_id": target_id, "objective": 99.9})
    assert slo.status_code == 201
    assert client.get("/api/obs/slos").json()["total"] == 1
    summary = client.get("/api/obs/summary").json()
    assert summary["items"][0]["availability"] == 100.0


def test_stats(client):
    target_id = _target(client)
    client.post("/api/obs/probe", json={"target_id": target_id, "simulate": True})
    stats = client.get("/api/obs/stats").json()
    assert stats["targets"] == 1
    assert stats["probes"] == 1
    assert stats["probes_up"] == 1


def test_manifest_and_crypto(client):
    assert client.get("/api/integration/manifest").json()["version"] == VERSION
    enc = client.post("/api/crypto/encrypt", json={"value": "x"}).json()["ciphertext"]
    assert client.post("/api/crypto/decrypt", json={"value": enc}).json()["plaintext"] == "x"


def test_write_requires_auth(client):
    del client.headers["X-Internal-Token"]
    assert client.post("/api/obs/targets", json={"name": "t", "url": "http://x"}).status_code == 401
