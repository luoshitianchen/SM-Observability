"""追踪规则 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TraceRuleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    service: str = Field(min_length=1, max_length=128)
    sample_rate: float = Field(ge=0.0, le=1.0, default=1.0)
    filter_expr: str = Field(default="", max_length=2000)


class TraceRuleUpdate(BaseModel):
    service: str | None = Field(default=None, min_length=1, max_length=128)
    sample_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    filter_expr: str | None = Field(default=None, max_length=2000)


class TraceRuleStatusUpdate(BaseModel):
    status: Literal["enabled", "disabled"]


class TraceRuleResponse(BaseModel):
    id: str
    name: str
    service: str
    sample_rate: float
    filter_expr: str
    status: str
    created_at: datetime | str
    updated_at: datetime | str


class TraceRuleListResponse(BaseModel):
    total: int
    items: list[TraceRuleResponse]
