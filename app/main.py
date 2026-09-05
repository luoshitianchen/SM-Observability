"""SM Observability —— 企业监控运维平台：目标探测、SLO、告警与可用性报表。"""

from __future__ import annotations

import ipaddress
import random
import socket
import urllib.parse
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from app import base

SERVICE = "sm-observability"
VERSION = "3.0.0"
NAME = "SM Observability"
DESCRIPTION = "企业监控运维平台：目标探测、SLO、告警与可用性报表"
PORT = 8330


def _now() -> str:
    return datetime.now(UTC).isoformat()


# 禁止探测的地址段：环回/内网/链路本地/云元数据/文档段，杜绝 SSRF 内网扫描
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return any(ip in net for net in _BLOCKED_NETWORKS)


def _safe_target_url(url: str) -> bool:
    """SSRF 防线：仅允许 http/https，且解析后的所有地址不得命中内网/环回/链路本地/云元数据。"""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        infos = socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
        return all(not _is_blocked_ip(ipaddress.ip_address(info[4][0])) for info in infos)
    except Exception:
        return False


def _init() -> None:
    with base.db_ctx() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS targets (
                id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, url TEXT NOT NULL,
                expected_status INTEGER NOT NULL DEFAULT 200, interval_seconds INTEGER NOT NULL DEFAULT 60,
                owner TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS probes (
                id TEXT PRIMARY KEY, target_id TEXT NOT NULL, status TEXT NOT NULL,
                latency_ms REAL NOT NULL, checked_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS slos (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, target_id TEXT NOT NULL,
                objective REAL NOT NULL, window_days INTEGER NOT NULL DEFAULT 30, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS alert_rules (
                id TEXT PRIMARY KEY, target_id TEXT NOT NULL, metric TEXT NOT NULL DEFAULT 'availability',
                threshold REAL NOT NULL, status TEXT NOT NULL DEFAULT 'ok', created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_probes_target ON probes(target_id, checked_at DESC);
            """
        )


app = base.create_app(
    service=SERVICE, name=NAME, description=DESCRIPTION, version=VERSION, port=PORT,
    dependencies=["sm-iam", "sm-event-bus", "sm-audit-log-center"],
    events=["probe.completed", "probe.failed", "alert.fired"],
    overview_fn=lambda _r: {
        "summary": {
            "targets": base.get_db().execute("SELECT COUNT(*) FROM targets").fetchone()[0],
            "probes": base.get_db().execute("SELECT COUNT(*) FROM probes").fetchone()[0],
        }
    },
)
_init()


class TargetIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    url: str = Field(min_length=2, max_length=500)
    expected_status: int = Field(default=200, ge=100, le=599)
    interval_seconds: int = Field(default=60, ge=5, le=86400)
    owner: str = Field(default="SRE团队", min_length=1, max_length=80)


class SloIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    target_id: str = Field(min_length=8)
    objective: float = Field(ge=90.0, le=100.0)
    window_days: int = Field(default=30, ge=1, le=365)


@app.get("/api/obs/targets")
def list_targets() -> dict[str, Any]:
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM targets ORDER BY created_at DESC").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/obs/targets", status_code=status.HTTP_201_CREATED)
def create_target(payload: TargetIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    if not _safe_target_url(payload.url):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "非法的探测目标地址（仅允许公网 http/https）")
    target_id = str(uuid.uuid4())
    with base.db_ctx() as conn:
        try:
            conn.execute("INSERT INTO targets VALUES (?,?,?,?,?,?,?)", (target_id, payload.name, payload.url, payload.expected_status, payload.interval_seconds, payload.owner, _now()))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status.HTTP_409_CONFLICT, "目标已存在") from exc
    return {"id": target_id, "name": payload.name}


@app.post("/api/obs/probe")
async def run_probe(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """对目标执行一次健康探测；simulate=true 时模拟探测（用于演练与测试）。"""
    base.require_internal_token(request)
    target_id = payload.get("target_id", "")
    simulate = bool(payload.get("simulate", False))
    with base.db_ctx() as conn:
        target = conn.execute("SELECT * FROM targets WHERE id=?", (target_id,)).fetchone()
        if not target:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "探测目标不存在")
        if simulate:
            probe_status = "up"
            latency = round(random.uniform(5, 120), 2)
        else:
            if not _safe_target_url(target["url"]):
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "探测目标地址不合规（SSRF 防护）")
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=1.5), trust_env=False) as client:
                    response = await client.get(target["url"])
                probe_status = "up" if response.status_code == target["expected_status"] else "down"
                latency = round(response.elapsed.total_seconds() * 1000, 2)
            except httpx.HTTPError:
                probe_status, latency = "down", 0.0
        probe_id = str(uuid.uuid4())
        conn.execute("INSERT INTO probes (id, target_id, status, latency_ms, checked_at) VALUES (?,?,?,?,?)", (probe_id, target_id, probe_status, latency, _now()))
        base.record_audit("probe.completed", "internal", f"target={target_id} status={probe_status} latency={latency}", getattr(request.state, "request_id", ""), getattr(request.state, "trace_id", ""), SERVICE)
    return {"id": probe_id, "target_id": target_id, "status": probe_status, "latency_ms": latency}


@app.get("/api/obs/targets/{target_id}/history")
def target_history(target_id: str, limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(500, limit))
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM targets WHERE id=?", (target_id,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "探测目标不存在")
        rows = conn.execute("SELECT * FROM probes WHERE target_id=? ORDER BY checked_at DESC LIMIT ?", (target_id, limit)).fetchall()
    return {"target_id": target_id, "items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/obs/slos", status_code=status.HTTP_201_CREATED)
def create_slo(payload: SloIn, request: Request) -> dict[str, Any]:
    base.require_internal_token(request)
    with base.db_ctx() as conn:
        if not conn.execute("SELECT 1 FROM targets WHERE id=?", (payload.target_id,)).fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "探测目标不存在")
        slo_id = str(uuid.uuid4())
        conn.execute("INSERT INTO slos VALUES (?,?,?,?,?,?)", (slo_id, payload.name, payload.target_id, payload.objective, payload.window_days, _now()))
    return {"id": slo_id, "name": payload.name, "objective": payload.objective}


@app.get("/api/obs/slos")
def list_slos() -> dict[str, Any]:
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM slos ORDER BY created_at DESC").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/obs/summary")
def summary() -> dict[str, Any]:
    with base.db_ctx() as conn:
        targets = conn.execute("SELECT * FROM targets").fetchall()
        items = []
        for target in targets:
            up = conn.execute("SELECT COUNT(*) FROM probes WHERE target_id=? AND status='up'", (target["id"],)).fetchone()[0]
            total = conn.execute("SELECT COUNT(*) FROM probes WHERE target_id=?", (target["id"],)).fetchone()[0]
            availability = round(up / total * 100, 3) if total else None
            items.append({"target_id": target["id"], "name": target["name"], "probes": total, "up": up, "availability": availability})
    return {"items": items, "total": len(items)}


@app.get("/api/obs/alerts")
def list_alerts() -> dict[str, Any]:
    with base.db_ctx() as conn:
        rows = conn.execute("SELECT * FROM alert_rules WHERE status='firing' ORDER BY created_at DESC").fetchall()
    return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/obs/stats")
def stats() -> dict[str, Any]:
    with base.db_ctx() as conn:
        def _count(sql: str) -> int:
            return conn.execute(sql).fetchone()[0]
        return {
            "targets": _count("SELECT COUNT(*) FROM targets"),
            "probes": _count("SELECT COUNT(*) FROM probes"),
            "probes_up": _count("SELECT COUNT(*) FROM probes WHERE status='up'"),
            "probes_down": _count("SELECT COUNT(*) FROM probes WHERE status='down'"),
            "slos": _count("SELECT COUNT(*) FROM slos"),
            "firing_alerts": _count("SELECT COUNT(*) FROM alert_rules WHERE status='firing'"),
        }