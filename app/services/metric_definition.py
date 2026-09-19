"""指标定义服务层：全生命周期管理。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import internal_write_allowed
from app.models.metric_definition import MetricDefinition
from app.repositories import metric_definition as repo
from app.schemas.metric_definition import MetricCreate, MetricUpdate
from app.services.audit import record_audit


def _metric_to_dict(m: MetricDefinition) -> dict:
    return {
        "id": m.id, "name": m.name, "metric_type": m.metric_type,
        "unit": m.unit or "", "description": m.description or "", "status": m.status,
        "created_at": m.created_at.isoformat() if m.created_at else "",
        "updated_at": m.updated_at.isoformat() if m.updated_at else "",
    }


class MetricService:
    @staticmethod
    async def list_metrics(
        session: AsyncSession, limit: int = 100, offset: int = 0,
        status_filter: str | None = None, metric_type: str | None = None,
        keyword: str | None = None,
    ) -> dict:
        metrics = await repo.list_metrics(
            session, limit=limit, offset=offset,
            status=status_filter, metric_type=metric_type, keyword=keyword,
        )
        total = await repo.count_metrics(
            session, status=status_filter, metric_type=metric_type, keyword=keyword
        )
        return {"total": total, "items": [_metric_to_dict(m) for m in metrics]}

    @staticmethod
    async def get_metric(session: AsyncSession, metric_id: str) -> dict:
        metric = await repo.get_metric(session, metric_id)
        if not metric:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "指标定义不存在")
        return _metric_to_dict(metric)

    @staticmethod
    async def create_metric(session: AsyncSession, payload: MetricCreate, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_metric_by_name(session, payload.name):
            raise HTTPException(status.HTTP_409_CONFLICT, "指标名称已存在")
        metric = MetricDefinition(
            id=str(uuid.uuid4()), name=payload.name, metric_type=payload.metric_type,
            unit=payload.unit or "", description=payload.description or "", status="enabled",
        )
        metric = await repo.create_metric(session, metric)
        await record_audit(session, "observability.metric_created", "internal",
                           f"name={payload.name}", request)
        return _metric_to_dict(metric)

    @staticmethod
    async def update_metric(
        session: AsyncSession, metric_id: str, payload: MetricUpdate, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        metric = await repo.get_metric(session, metric_id)
        if not metric:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "指标定义不存在")
        if payload.unit is not None:
            metric.unit = payload.unit
        if payload.description is not None:
            metric.description = payload.description
        metric = await repo.update_metric(session, metric)
        await record_audit(session, "observability.metric_updated", "internal",
                           f"metric_id={metric_id}", request)
        return _metric_to_dict(metric)

    @staticmethod
    async def update_status(
        session: AsyncSession, metric_id: str, new_status: str, request: Request
    ) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        metric = await repo.get_metric(session, metric_id)
        if not metric:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "指标定义不存在")
        metric.status = new_status
        metric = await repo.update_metric(session, metric)
        await record_audit(session, "observability.metric_status_changed", "internal",
                           f"metric_id={metric_id} status={new_status}", request)
        return _metric_to_dict(metric)

    @staticmethod
    async def delete_metric(session: AsyncSession, metric_id: str, request: Request) -> dict:
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        metric = await repo.get_metric(session, metric_id)
        if not metric:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "指标定义不存在")
        # 引用完整性：存在启用的告警规则引用时禁止删除
        used = await repo.count_alerts_by_metric(session, metric.name)
        if used > 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"指标被 {used} 条启用告警规则引用，禁止删除"
            )
        name = metric.name
        await repo.delete_metric(session, metric)
        await record_audit(session, "observability.metric_deleted", "internal",
                           f"metric_id={metric_id} name={name}", request)
        return {"deleted": True, "id": metric_id}
