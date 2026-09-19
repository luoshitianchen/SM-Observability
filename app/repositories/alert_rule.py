"""告警规则仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert_rule import AlertRule


async def get_alert_rule(session: AsyncSession, rule_id: str) -> AlertRule | None:
    result = await session.execute(select(AlertRule).where(AlertRule.id == rule_id))
    return result.scalar_one_or_none()


async def get_alert_rule_by_name(session: AsyncSession, name: str) -> AlertRule | None:
    result = await session.execute(select(AlertRule).where(AlertRule.name == name))
    return result.scalar_one_or_none()


async def list_alert_rules(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    status: str | None = None, severity: str | None = None,
    metric_name: str | None = None, keyword: str | None = None,
) -> list[AlertRule]:
    stmt = select(AlertRule).order_by(AlertRule.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(AlertRule.status == status)
    if severity:
        stmt = stmt.where(AlertRule.severity == severity)
    if metric_name:
        stmt = stmt.where(AlertRule.metric_name == metric_name)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(AlertRule.name.like(like), AlertRule.metric_name.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_alert_rules(
    session: AsyncSession, status: str | None = None, severity: str | None = None,
    metric_name: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(AlertRule.id))
    if status:
        stmt = stmt.where(AlertRule.status == status)
    if severity:
        stmt = stmt.where(AlertRule.severity == severity)
    if metric_name:
        stmt = stmt.where(AlertRule.metric_name == metric_name)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(AlertRule.name.like(like), AlertRule.metric_name.like(like)))
    result = await session.execute(stmt)
    return result.scalar_one()


async def create_alert_rule(session: AsyncSession, rule: AlertRule) -> AlertRule:
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def update_alert_rule(session: AsyncSession, rule: AlertRule) -> AlertRule:
    await session.commit()
    await session.refresh(rule)
    return rule


async def delete_alert_rule(session: AsyncSession, rule: AlertRule) -> None:
    await session.delete(rule)
    await session.commit()
