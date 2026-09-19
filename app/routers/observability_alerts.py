"""告警规则管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.alert_rule import AlertRuleCreate, AlertRuleStatusUpdate, AlertRuleUpdate
from app.services.alert_rule import AlertRuleService

router = APIRouter(prefix="/api/observability/alerts", tags=["observability-alerts"])


@router.get("")
async def list_alert_rules(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None, max_length=16),
    metric_name: str | None = Query(default=None, max_length=128),
    keyword: str | None = Query(default=None, max_length=128),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AlertRuleService.list_rules(
        session, limit=limit, offset=offset,
        status_filter=status_filter, severity=severity,
        metric_name=metric_name, keyword=keyword,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    payload: AlertRuleCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AlertRuleService.create_rule(session, payload, request)


@router.get("/{rule_id}")
async def get_alert_rule(
    rule_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AlertRuleService.get_rule(session, rule_id)


@router.patch("/{rule_id}")
async def update_alert_rule(
    rule_id: str, payload: AlertRuleUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AlertRuleService.update_rule(session, rule_id, payload, request)


@router.patch("/{rule_id}/status")
async def update_alert_rule_status(
    rule_id: str, payload: AlertRuleStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AlertRuleService.update_status(session, rule_id, payload.status, request)


@router.delete("/{rule_id}", status_code=status.HTTP_200_OK)
async def delete_alert_rule(
    rule_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await AlertRuleService.delete_rule(session, rule_id, request)
