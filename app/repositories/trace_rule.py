"""追踪规则仓储层。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trace_rule import TraceRule


async def get_trace_rule(session: AsyncSession, rule_id: str) -> TraceRule | None:
    result = await session.execute(select(TraceRule).where(TraceRule.id == rule_id))
    return result.scalar_one_or_none()


async def get_trace_rule_by_name(session: AsyncSession, name: str) -> TraceRule | None:
    result = await session.execute(select(TraceRule).where(TraceRule.name == name))
    return result.scalar_one_or_none()


async def list_trace_rules(
    session: AsyncSession, limit: int = 100, offset: int = 0,
    status: str | None = None, service: str | None = None, keyword: str | None = None,
) -> list[TraceRule]:
    stmt = select(TraceRule).order_by(TraceRule.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(TraceRule.status == status)
    if service:
        stmt = stmt.where(TraceRule.service == service)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(TraceRule.name.like(like), TraceRule.service.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_trace_rules(
    session: AsyncSession, status: str | None = None,
    service: str | None = None, keyword: str | None = None,
) -> int:
    stmt = select(func.count(TraceRule.id))
    if status:
        stmt = stmt.where(TraceRule.status == status)
    if service:
        stmt = stmt.where(TraceRule.service == service)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(TraceRule.name.like(like), TraceRule.service.like(like)))
    result = await session.execute(stmt)
    return result.scalar_one()


async def create_trace_rule(session: AsyncSession, rule: TraceRule) -> TraceRule:
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def update_trace_rule(session: AsyncSession, rule: TraceRule) -> TraceRule:
    await session.commit()
    await session.refresh(rule)
    return rule


async def delete_trace_rule(session: AsyncSession, rule: TraceRule) -> None:
    await session.delete(rule)
    await session.commit()
