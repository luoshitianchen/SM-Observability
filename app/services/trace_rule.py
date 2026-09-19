"""追踪规则服务层：采样配置管理。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.trace_rule import TraceRule
from app.repositories import trace_rule as repo
from app.schemas.trace_rule import TraceRuleCreate, TraceRuleUpdate
from app.services.audit import record_audit


def _rule_to_dict(t: TraceRule) -> dict:
    return {
        "id": t.id, "name": t.name, "service": t.service,
        "sample_rate": t.sample_rate, "filter_expr": t.filter_expr or "",
        "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "updated_at": t.updated_at.isoformat() if t.updated_at else "",
    }


class TraceRuleService:
    @staticmethod
    async def list_rules(
        session: AsyncSession, limit: int = 100, offset: int = 0,
        status_filter: str | None = None, service: str | None = None,
        keyword: str | None = None,
    ) -> dict:
        rules = await repo.list_trace_rules(
            session, limit=limit, offset=offset,
            status=status_filter, service=service, keyword=keyword,
        )
        total = await repo.count_trace_rules(
            session, status=status_filter, service=service, keyword=keyword
        )
        return {"total": total, "items": [_rule_to_dict(t) for t in rules]}

    @staticmethod
    async def get_rule(session: AsyncSession, rule_id: str) -> dict:
        rule = await repo.get_trace_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "追踪规则不存在")
        return _rule_to_dict(rule)

    @staticmethod
    async def create_rule(session: AsyncSession, payload: TraceRuleCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_trace_rule_by_name(session, payload.name):
            raise HTTPException(status.HTTP_409_CONFLICT, "追踪规则名称已存在")
        rule = TraceRule(
            id=str(uuid.uuid4()), name=payload.name, service=payload.service,
            sample_rate=payload.sample_rate, filter_expr=payload.filter_expr or "",
            status="enabled",
        )
        rule = await repo.create_trace_rule(session, rule)
        await record_audit(session, "observability.trace_rule_created", "internal",
                           f"name={payload.name}", request)
        return _rule_to_dict(rule)

    @staticmethod
    async def update_rule(
        session: AsyncSession, rule_id: str, payload: TraceRuleUpdate, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        rule = await repo.get_trace_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "追踪规则不存在")
        if payload.service is not None:
            rule.service = payload.service
        if payload.sample_rate is not None:
            rule.sample_rate = payload.sample_rate
        if payload.filter_expr is not None:
            rule.filter_expr = payload.filter_expr
        rule = await repo.update_trace_rule(session, rule)
        await record_audit(session, "observability.trace_rule_updated", "internal",
                           f"rule_id={rule_id}", request)
        return _rule_to_dict(rule)

    @staticmethod
    async def update_status(
        session: AsyncSession, rule_id: str, new_status: str, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        rule = await repo.get_trace_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "追踪规则不存在")
        rule.status = new_status
        rule = await repo.update_trace_rule(session, rule)
        await record_audit(session, "observability.trace_rule_status_changed", "internal",
                           f"rule_id={rule_id} status={new_status}", request)
        return _rule_to_dict(rule)

    @staticmethod
    async def delete_rule(session: AsyncSession, rule_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        rule = await repo.get_trace_rule(session, rule_id)
        if not rule:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "追踪规则不存在")
        name = rule.name
        await repo.delete_trace_rule(session, rule)
        await record_audit(session, "observability.trace_rule_deleted", "internal",
                           f"rule_id={rule_id} name={name}", request)
        return {"deleted": True, "id": rule_id}
