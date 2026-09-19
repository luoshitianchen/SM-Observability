"""指标定义管理路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.metric_definition import MetricCreate, MetricStatusUpdate, MetricUpdate
from app.services.metric_definition import MetricService

router = APIRouter(prefix="/api/observability/metrics", tags=["observability-metrics"])


@router.get("")
async def list_metrics(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    metric_type: str | None = Query(default=None, max_length=16),
    keyword: str | None = Query(default=None, max_length=128),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MetricService.list_metrics(
        session, limit=limit, offset=offset,
        status_filter=status_filter, metric_type=metric_type, keyword=keyword,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_metric(
    payload: MetricCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MetricService.create_metric(session, payload, request)


@router.get("/{metric_id}")
async def get_metric(
    metric_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MetricService.get_metric(session, metric_id)


@router.patch("/{metric_id}")
async def update_metric(
    metric_id: str, payload: MetricUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MetricService.update_metric(session, metric_id, payload, request)


@router.patch("/{metric_id}/status")
async def update_metric_status(
    metric_id: str, payload: MetricStatusUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MetricService.update_status(session, metric_id, payload.status, request)


@router.delete("/{metric_id}", status_code=status.HTTP_200_OK)
async def delete_metric(
    metric_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await MetricService.delete_metric(session, metric_id, request)
