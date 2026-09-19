"""指标定义仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metric_definition import MetricDefinition


async def get_metric(session: AsyncSession, metric_id: str) -> MetricDefinition | None:
    result = await session.execute(select(MetricDefinition).where(MetricDefinition.id == metric_id))
    return result.scalar_one_or_none()


async def get_metric_by_name(session: AsyncSession, name: str) -> MetricDefinition | None:
    result = await session.execute(select(MetricDefinition).where(MetricDefinition.name == name))
    return result.scalar_one_or_none()


async def count_alerts_by_metric(session: AsyncSession, metric_name: str) -> int:
    from app.models.alert_rule import AlertRule

    result = await session.execute(
        select(func.count(AlertRule.id)).where(
            AlertRule.metric_name == metric_name, AlertRule.status == "enabled"
        )
    )
    return result.scalar_one()


async def list_metrics(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    status: str | None = None, metric_type: str | None = None, keyword: str | None = None,
) -> list[MetricDefinition]:
    stmt = select(MetricDefinition).order_by(MetricDefinition.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(MetricDefinition.status == status)
    if metric_type:
        stmt = stmt.where(MetricDefinition.metric_type == metric_type)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(MetricDefinition.name.like(like), MetricDefinition.description.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_metrics(
    session: AsyncSession, status: str | None = None,
    metric_type: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(MetricDefinition.id))
    if status:
        stmt = stmt.where(MetricDefinition.status == status)
    if metric_type:
        stmt = stmt.where(MetricDefinition.metric_type == metric_type)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(MetricDefinition.name.like(like), MetricDefinition.description.like(like)))
    result = await session.execute(stmt)
    return result.scalar_one()


async def create_metric(session: AsyncSession, metric: MetricDefinition) -> MetricDefinition:
    session.add(metric)
    await session.commit()
    await session.refresh(metric)
    return metric


async def update_metric(session: AsyncSession, metric: MetricDefinition) -> MetricDefinition:
    await session.commit()
    await session.refresh(metric)
    return metric


async def delete_metric(session: AsyncSession, metric: MetricDefinition) -> None:
    await session.delete(metric)
    await session.commit()
