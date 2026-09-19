"""告警规则 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AlertRuleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    metric_name: str = Field(min_length=1, max_length=128)
    condition: Literal["above", "below", "equals"] = "above"
    threshold: float = Field(...)
    duration_seconds: int = Field(default=60, ge=0, le=86400)
    severity: Literal["info", "warning", "critical"] = "warning"
    channels: list[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=2000)


class AlertRuleUpdate(BaseModel):
    condition: Literal["above", "below", "equals"] | None = None
    threshold: float | None = None
    duration_seconds: int | None = Field(default=None, ge=0, le=86400)
    severity: Literal["info", "warning", "critical"] | None = None
    channels: list[str] | None = None
    description: str | None = Field(default=None, max_length=2000)


class AlertRuleStatusUpdate(BaseModel):
    status: Literal["enabled", "disabled"]


class AlertRuleResponse(BaseModel):
    id: str
    name: str
    metric_name: str
    condition: str
    threshold: float
    duration_seconds: int
    severity: str
    channels: list[str]
    status: str
    description: str
    created_at: datetime | str
    updated_at: datetime | str


class AlertRuleListResponse(BaseModel):
    total: int
    items: list[AlertRuleResponse]
