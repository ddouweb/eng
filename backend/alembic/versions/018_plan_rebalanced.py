"""plan last rebalanced at

Revision ID: 018_plan_rebalanced
Revises: 017_weekly_settlement
Create Date: 2026-07-24

learning_plan 加 last_rebalanced_at（nullable）：记录最近一次「重新平衡计划」
（手动把剩余未掌握词重新摊到 deadline 前的未来学习日）的时间，供前端展示与去抖。

nullable 列两端（upgrade/downgrade）安全，无需回填。
注：revision id ≤32 字符适配 alembic_version.version_num (VARCHAR(32))。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "018_plan_rebalanced"
down_revision: Union[str, None] = "017_weekly_settlement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learning_plan",
        sa.Column("last_rebalanced_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("learning_plan", "last_rebalanced_at")
