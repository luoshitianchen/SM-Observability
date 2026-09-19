"""SM-Observability 业务深化测试：指标/追踪规则/告警规则全生命周期。"""
from __future__ import annotations

import pytest

H = {"X-Internal-Token": "test-internal-key-12345"}


async def _create_metric(client, name: str, mtype: str = "gauge") -> dict:
    resp = await client.post("/api/observability/metrics", json={
        "name": name, "metric_type": mtype, "unit": "ms", "description": "测试指标",
    }, headers=H)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_alert(client, name: str, metric_name: str) -> dict:
    resp = await client.post("/api/observability/alerts", json={
        "name": name, "metric_name": metric_name, "condition": "above",
        "threshold": 90.0, "duration_seconds": 120, "severity": "critical",
        "channels": ["dingtalk"],
    }, headers=H)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ═══════════════════════════════════════════════════════════
# 指标定义
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_metric_success(client):
    data = await _create_metric(client, "http_request_duration_seconds", "histogram")
    assert data["name"] == "http_request_duration_seconds"
    assert data["metric_type"] == "histogram"
    assert data["status"] == "enabled"


@pytest.mark.asyncio
async def test_create_metric_requires_token(client):
    resp = await client.post("/api/observability/metrics", json={"name": "m_noauth"})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_metric_duplicate_name(client):
    await _create_metric(client, "m_dup")
    resp = await client.post("/api/observability/metrics", json={"name": "m_dup"}, headers=H)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_metrics_filter_and_keyword(client):
    await _create_metric(client, "m_filt", "counter")
    resp = await client.get("/api/observability/metrics?keyword=m_filt", headers=H)
    assert resp.status_code == 200
    assert any(m["name"] == "m_filt" for m in resp.json()["items"])
    resp2 = await client.get("/api/observability/metrics?metric_type=counter", headers=H)
    assert all(m["metric_type"] == "counter" for m in resp2.json()["items"])


@pytest.mark.asyncio
async def test_get_metric_not_found(client):
    resp = await client.get("/api/observability/metrics/no-such-id", headers=H)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_metric(client):
    m = await _create_metric(client, "m_upd")
    resp = await client.patch(f"/api/observability/metrics/{m['id']}", json={
        "unit": "bytes", "description": "更新描述",
    }, headers=H)
    assert resp.status_code == 200
    assert resp.json()["unit"] == "bytes"


@pytest.mark.asyncio
async def test_disable_metric(client):
    m = await _create_metric(client, "m_dis")
    resp = await client.patch(f"/api/observability/metrics/{m['id']}/status", json={
        "status": "disabled",
    }, headers=H)
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"


@pytest.mark.asyncio
async def test_delete_metric_referenced_blocked(client):
    await _create_metric(client, "m_used")
    await _create_alert(client, "alert-used", "m_used")
    # 需先按名称找到 metric id
    lst = await client.get("/api/observability/metrics?keyword=m_used", headers=H)
    mid = next(x["id"] for x in lst.json()["items"] if x["name"] == "m_used")
    resp = await client.delete(f"/api/observability/metrics/{mid}", headers=H)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_unused_metric_ok(client):
    m = await _create_metric(client, "m_free")
    resp = await client.delete(f"/api/observability/metrics/{m['id']}", headers=H)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


# ═══════════════════════════════════════════════════════════
# 追踪规则
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_trace_rule_success(client):
    resp = await client.post("/api/observability/trace-rules", json={
        "name": "trace-high-traffic", "service": "sm-order",
        "sample_rate": 0.5, "filter_expr": "http.status_code>=500",
    }, headers=H)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["sample_rate"] == 0.5
    assert data["status"] == "enabled"


@pytest.mark.asyncio
async def test_create_trace_rule_duplicate_name(client):
    await client.post("/api/observability/trace-rules", json={
        "name": "trace-dup", "service": "svc-a", "sample_rate": 1.0,
    }, headers=H)
    resp = await client.post("/api/observability/trace-rules", json={
        "name": "trace-dup", "service": "svc-b",
    }, headers=H)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_trace_rule_sample_rate_out_of_range(client):
    resp = await client.post("/api/observability/trace-rules", json={
        "name": "trace-badrate", "service": "svc-c", "sample_rate": 1.5,
    }, headers=H)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_trace_rules_filter(client):
    await client.post("/api/observability/trace-rules", json={
        "name": "trace-list", "service": "svc-list", "sample_rate": 0.3,
    }, headers=H)
    resp = await client.get("/api/observability/trace-rules?service=svc-list", headers=H)
    assert resp.status_code == 200
    assert all(r["service"] == "svc-list" for r in resp.json()["items"])
    resp2 = await client.get("/api/observability/trace-rules?keyword=trace-list", headers=H)
    assert any(r["name"] == "trace-list" for r in resp2.json()["items"])


@pytest.mark.asyncio
async def test_update_trace_rule(client):
    created = await client.post("/api/observability/trace-rules", json={
        "name": "trace-upd", "service": "svc-upd", "sample_rate": 0.1,
    }, headers=H)
    rid = created.json()["id"]
    resp = await client.patch(f"/api/observability/trace-rules/{rid}", json={
        "sample_rate": 0.8, "filter_expr": "delay>1s",
    }, headers=H)
    assert resp.status_code == 200
    assert resp.json()["sample_rate"] == 0.8


@pytest.mark.asyncio
async def test_disable_trace_rule(client):
    created = await client.post("/api/observability/trace-rules", json={
        "name": "trace-dis", "service": "svc-dis", "sample_rate": 1.0,
    }, headers=H)
    rid = created.json()["id"]
    resp = await client.patch(f"/api/observability/trace-rules/{rid}/status", json={
        "status": "disabled",
    }, headers=H)
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"


@pytest.mark.asyncio
async def test_delete_trace_rule(client):
    created = await client.post("/api/observability/trace-rules", json={
        "name": "trace-del", "service": "svc-del", "sample_rate": 1.0,
    }, headers=H)
    rid = created.json()["id"]
    resp = await client.delete(f"/api/observability/trace-rules/{rid}", headers=H)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


# ═══════════════════════════════════════════════════════════
# 告警规则
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_alert_success(client):
    await _create_metric(client, "alert-metric-ok")
    data = await _create_alert(client, "alert-ok", "alert-metric-ok")
    assert data["name"] == "alert-ok"
    assert data["threshold"] == 90.0
    assert data["channels"] == ["dingtalk"]
    assert data["severity"] == "critical"


@pytest.mark.asyncio
async def test_create_alert_duplicate_name(client):
    await _create_metric(client, "alert-metric-dup")
    await _create_alert(client, "alert-dup", "alert-metric-dup")
    resp = await client.post("/api/observability/alerts", json={
        "name": "alert-dup", "metric_name": "alert-metric-dup", "threshold": 1,
    }, headers=H)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_alert_undefined_metric(client):
    resp = await client.post("/api/observability/alerts", json={
        "name": "alert-nometric", "metric_name": "not_defined_metric", "threshold": 1,
    }, headers=H)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_alerts_filter(client):
    await _create_metric(client, "alert-metric-list")
    await _create_alert(client, "alert-list", "alert-metric-list")
    resp = await client.get("/api/observability/alerts?severity=critical", headers=H)
    assert resp.status_code == 200
    assert all(a["severity"] == "critical" for a in resp.json()["items"])
    resp2 = await client.get("/api/observability/alerts?metric_name=alert-metric-list", headers=H)
    assert all(a["metric_name"] == "alert-metric-list" for a in resp2.json()["items"])
    resp3 = await client.get("/api/observability/alerts?keyword=alert-list", headers=H)
    assert any(a["name"] == "alert-list" for a in resp3.json()["items"])


@pytest.mark.asyncio
async def test_update_alert(client):
    await _create_metric(client, "alert-metric-upd")
    alert = await _create_alert(client, "alert-upd", "alert-metric-upd")
    resp = await client.patch(f"/api/observability/alerts/{alert['id']}", json={
        "threshold": 95.5, "channels": ["sms", "email"], "severity": "warning",
    }, headers=H)
    assert resp.status_code == 200
    assert resp.json()["threshold"] == 95.5
    assert "email" in resp.json()["channels"]
    assert resp.json()["severity"] == "warning"


@pytest.mark.asyncio
async def test_disable_alert(client):
    await _create_metric(client, "alert-metric-dis")
    alert = await _create_alert(client, "alert-dis", "alert-metric-dis")
    resp = await client.patch(f"/api/observability/alerts/{alert['id']}/status", json={
        "status": "disabled",
    }, headers=H)
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"


@pytest.mark.asyncio
async def test_delete_alert(client):
    await _create_metric(client, "alert-metric-del")
    alert = await _create_alert(client, "alert-del", "alert-metric-del")
    resp = await client.delete(f"/api/observability/alerts/{alert['id']}", headers=H)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
