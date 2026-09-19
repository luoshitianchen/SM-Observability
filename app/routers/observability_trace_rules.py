"""追踪规则管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.trace_rule import TraceRuleCreate, TraceRuleStatusUpdate, TraceRuleUpdate
from app.services.trace_rule import TraceRuleService

router = APIRouter(prefix="/api/observability/trace-rules", tags=["observability-trace-rules"])


@router.get("")
async def list_trace_rules(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    service: str | None = Query(default=None, max_length=128),
    keyword: str | None = Query(default=None, max_length=128),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TraceRuleService.list_rules(
        session, limit=limit, offset=offset,
        status_filter=status_filter, service=service, keyword=keyword,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_trace_rule(
    payload: TraceRuleCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TraceRuleService.create_rule(session, payload, request)


@router.get("/{rule_id}")
async def get_trace_rule(
    rule_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TraceRuleService.get_rule(session, rule_id)


@router.patch("/{rule_id}")
async def update_trace_rule(
    rule_id: str, payload: TraceRuleUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TraceRuleService.update_rule(session, rule_id, payload, request)


@router.patch("/{rule_id}/status")
async def update_trace_rule_status(
    rule_id: str, payload: TraceRuleStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TraceRuleService.update_status(session, rule_id, payload.status, request)


@router.delete("/{rule_id}", status_code=status.HTTP_200_OK)
async def delete_trace_rule(
    rule_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TraceRuleService.delete_rule(session, rule_id, request)
