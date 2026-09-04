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
    return client.post("/api/obs/targets", json={"name": name, "url": "http://example.com/health", "owner": "SRE"}).json()["id"]


def test_health_and_version(client):
    r = client.get("/health", headers={"X-Request-Id": "suite-test"})
    assert r.status_code == 200
    assert r.json()["version"] == VERSION


def test_target_ssrf_rejected(client):
    """SSRF 防线：环回/内网/链路本地/云元数据/非 http(s) 一律拒绝。"""
    evil = [
        "http://127.0.0.1:8200/health",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "file:///etc/passwd",
        "ftp://example.com/x",
    ]
    for i, url in enumerate(evil):
        r = client.post("/api/obs/targets", json={"name": f"evil{i}", "url": url})
        assert r.status_code == 400, f"应拒绝 {url}, got {r.status_code}"
    assert client.get("/api/obs/targets").json()["total"] == 0


def test_probe_rejects_stored_blocked_url(client):
    """probe 阶段二次防线：即使 DB 中已存在内网目标，探测时仍被拒绝。"""
    import uuid

    from app import base

    with base.db_ctx() as conn:
        tid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO targets (id, name, url, expected_status, interval_seconds, owner, created_at) VALUES (?,?,?,?,?,?,?)",
            (tid, "legacy-internal", "http://127.0.0.1:8200/health", 200, 60, "SRE", "2026-01-01T00:00:00+00:00"),
        )
    r = client.post("/api/obs/probe", json={"target_id": tid, "simulate": False})
    assert r.status_code == 400, f"探测阶段应拒绝内网目标, got {r.status_code}"


def test_target_lifecycle(client):
    _target(client)
    assert client.post("/api/obs/targets", json={"name": "fusion", "url": "http://example.com/other"}).status_code == 409
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
