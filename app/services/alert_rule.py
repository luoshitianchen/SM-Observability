"""告警规则服务层：阈值与通知渠道管理。"""
from __future__ import annotations

import json
import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.alert_rule import AlertRule
from app.repositories import alert_rule as repo
from app.repositories import metric_definition as metric_repo
from app.schemas.alert_rule import AlertRuleCreate, AlertRuleUpdate
from app.services.audit import record_audit


def _alert_to_dict(a: AlertRule) -> dict:
    try:
        channels = json.loads(a.channels or "[]")
    except (json.JSONDecodeError, TypeError):
        channels = []
    return {
        "id": a.id, "name": a.name, "metric_name": a.metric_name,
        "condition": a.condition, "threshold": a.threshold,
        "duration_seconds": a.duration_seconds, "severity": a.severity,
        "channels": channels, "status": a.status, "description": a.description or "",
        "created_at": a.created_at.isoformat() if a.created_at else "",
        "updated_at": a.updated_at.isoformat() if a.updated_at else "",
    }


class AlertRuleService:
    @staticmethod
    async def list_rules(
        session: AsyncSession, limit: int = 100, offset: int = 0,
        status_filter: str | None = None, severity: str | None = None,
        metric_name: str | None = None, keyword: str | None = None,
    ) -> dict:
        rules = await repo.list_alert_rules(
            session, limit=limit, offset=offset,
            status=status_filter, severity=severity,
            metric_name=metric_name, keyword=keyword,
        )
        total = await repo.count_alert_rules(
            session, status=status_filter, severity=severity,
            metric_name=metric_name, keyword=keyword,
        )
        return {"total": total, "items": [_alert_to_dict(a) for a in rules]}

    @staticmethod
    async def get_rule(session: AsyncSession, rule_id: str) -> dict:
        rule = await repo.get_alert_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "告警规则不存在")
        return _alert_to_dict(rule)

    @staticmethod
    async def create_rule(session: AsyncSession, payload: AlertRuleCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_alert_rule_by_name(session, payload.name):
            raise HTTPException(status.HTTP_409_CONFLICT, "告警规则名称已存在")
        # 引用完整性：绑定的指标定义必须存在
        metric = await metric_repo.get_metric_by_name(session, payload.metric_name)
        if not metric:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"指标 {payload.metric_name} 未定义")
        rule = AlertRule(
            id=str(uuid.uuid4()), name=payload.name, metric_name=payload.metric_name,
            condition=payload.condition, threshold=payload.threshold,
            duration_seconds=payload.duration_seconds, severity=payload.severity,
            channels=json.dumps(payload.channels or [], ensure_ascii=False),
            description=payload.description or "", status="enabled",
        )
        rule = await repo.create_alert_rule(session, rule)
        await record_audit(session, "observability.alert_rule_created", "internal",
                           f"name={payload.name}", request)
        return _alert_to_dict(rule)

    @staticmethod
    async def update_rule(
        session: AsyncSession, rule_id: str, payload: AlertRuleUpdate, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        rule = await repo.get_alert_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "告警规则不存在")
        if payload.condition is not None:
            rule.condition = payload.condition
        if payload.threshold is not None:
            rule.threshold = payload.threshold
        if payload.duration_seconds is not None:
            rule.duration_seconds = payload.duration_seconds
        if payload.severity is not None:
            rule.severity = payload.severity
        if payload.channels is not None:
            rule.channels = json.dumps(payload.channels, ensure_ascii=False)
        if payload.description is not None:
            rule.description = payload.description
        rule = await repo.update_alert_rule(session, rule)
        await record_audit(session, "observability.alert_rule_updated", "internal",
                           f"rule_id={rule_id}", request)
        return _alert_to_dict(rule)

    @staticmethod
    async def update_status(
        session: AsyncSession, rule_id: str, new_status: str, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        rule = await repo.get_alert_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "告警规则不存在")
        rule.status = new_status
        rule = await repo.update_alert_rule(session, rule)
        await record_audit(session, "observability.alert_rule_status_changed", "internal",
                           f"rule_id={rule_id} status={new_status}", request)
        return _alert_to_dict(rule)

    @staticmethod
    async def delete_rule(session: AsyncSession, rule_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        rule = await repo.get_alert_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "告警规则不存在")
        name = rule.name
        await repo.delete_alert_rule(session, rule)
        await record_audit(session, "observability.alert_rule_deleted", "internal",
                           f"rule_id={rule_id} name={name}", request)
        return {"deleted": True, "id": rule_id}
