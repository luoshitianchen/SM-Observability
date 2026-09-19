"""指标定义 Pydantic 模型。"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MetricCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128, pattern=r"^[a-zA-Z0-9_:.-]+$")
    metric_type: Literal["counter", "gauge", "histogram"] = "gauge"
    unit: str = Field(default="", max_length=32)
    description: str = Field(default="", max_length=2000)


class MetricUpdate(BaseModel):
    unit: str | None = Field(default=None, max_length=32)
    description: str | None = Field(default=None, max_length=2000)


class MetricStatusUpdate(BaseModel):
    status: Literal["enabled", "disabled"]


class MetricResponse(BaseModel):
    id: str
    name: str
    metric_type: str
    unit: str
    description: str
    status: str
    created_at: datetime | str
    updated_at: datetime | str


class MetricListResponse(BaseModel):
    total: int
    items: list[MetricResponse]
