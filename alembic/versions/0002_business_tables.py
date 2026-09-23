"""新增业务表：告警规则、指标定义与链路追踪规则。

Revision ID: 0002_business_tables
Revises: 0001_initial
Create Date: 2026-09-23
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# 本迁移的版本号，下游 0003 及以后迁移以此为 down_revision
revision: str = '0002_business_tables'
# 上一版本，承接 0001_initial
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### Alembic 自动生成开始，按模型元数据建立业务表 ###
    # 告警规则表：定义指标触发告警的阈值与通知渠道
    op.create_table('alert_rules',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('metric_name', sa.String(length=128), nullable=False),
    sa.Column('condition', sa.String(length=16), nullable=False),
    sa.Column('threshold', sa.Float(), nullable=False),
    sa.Column('duration_seconds', sa.Integer(), nullable=False),
    sa.Column('severity', sa.String(length=16), nullable=False),
    sa.Column('channels', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_rules_metric_name'), 'alert_rules', ['metric_name'], unique=False)
    op.create_index(op.f('ix_alert_rules_name'), 'alert_rules', ['name'], unique=True)
    op.create_index(op.f('ix_alert_rules_severity'), 'alert_rules', ['severity'], unique=False)
    op.create_index(op.f('ix_alert_rules_status'), 'alert_rules', ['status'], unique=False)
    # 指标定义表：登记可观测指标的元数据
    op.create_table('metric_definitions',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('metric_type', sa.String(length=16), nullable=False),
    sa.Column('unit', sa.String(length=32), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_metric_definitions_metric_type'), 'metric_definitions', ['metric_type'], unique=False)
    op.create_index(op.f('ix_metric_definitions_name'), 'metric_definitions', ['name'], unique=True)
    op.create_index(op.f('ix_metric_definitions_status'), 'metric_definitions', ['status'], unique=False)
    # 链路追踪规则表：按服务配置采样率与过滤条件
    op.create_table('trace_rules',
    sa.Column('id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('service', sa.String(length=128), nullable=False),
    sa.Column('sample_rate', sa.Float(), nullable=False),
    sa.Column('filter_expr', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_trace_rules_name'), 'trace_rules', ['name'], unique=True)
    op.create_index(op.f('ix_trace_rules_service'), 'trace_rules', ['service'], unique=False)
    op.create_index(op.f('ix_trace_rules_status'), 'trace_rules', ['status'], unique=False)
    # ### Alembic 自动生成结束 ###


def downgrade() -> None:
    # ### Alembic 自动生成开始，按逆序删除业务表与索引 ###
    op.drop_index(op.f('ix_trace_rules_status'), table_name='trace_rules')
    op.drop_index(op.f('ix_trace_rules_service'), table_name='trace_rules')
    op.drop_index(op.f('ix_trace_rules_name'), table_name='trace_rules')
    op.drop_table('trace_rules')
    op.drop_index(op.f('ix_metric_definitions_status'), table_name='metric_definitions')
    op.drop_index(op.f('ix_metric_definitions_name'), table_name='metric_definitions')
    op.drop_index(op.f('ix_metric_definitions_metric_type'), table_name='metric_definitions')
    op.drop_table('metric_definitions')
    op.drop_index(op.f('ix_alert_rules_status'), table_name='alert_rules')
    op.drop_index(op.f('ix_alert_rules_severity'), table_name='alert_rules')
    op.drop_index(op.f('ix_alert_rules_name'), table_name='alert_rules')
    op.drop_index(op.f('ix_alert_rules_metric_name'), table_name='alert_rules')
    op.drop_table('alert_rules')
    # ### Alembic 自动生成结束 ###
