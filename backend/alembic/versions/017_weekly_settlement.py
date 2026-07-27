"""weekly settlement

Revision ID: 017_weekly_settlement
Revises: 016_mastery_srs
Create Date: 2026-07-24

每周奖励结算的幂等快照表（一人一周一行，uq_member_week_settlement）。
懒触发结算（无 cron），bonus 只来自坚持分+计划分（与逐题难度 XP 不重叠），
封顶 30/周。id/member_id 用 BigInteger 以匹配 member.id（bigint），
否则 MariaDB errno 150（见 015 迁移同类注释）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "017_weekly_settlement"
down_revision: Union[str, None] = "016_mastery_srs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weekly_settlement",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("member_id", sa.BigInteger(),
                  sa.ForeignKey("member.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_key", sa.String(length=10), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("login_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("difficulty_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("plan_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("real_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_words_learned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("plan_completion", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("bonus_xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("freeze_granted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("badges_granted", sa.JSON(), nullable=True),
        sa.Column("plan_health", sa.JSON(), nullable=True),
        sa.Column("settled_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("member_id", "week_key", name="uq_member_week_settlement"),
    )
    op.create_index("ix_weekly_settlement_member_id", "weekly_settlement", ["member_id"])


def downgrade() -> None:
    op.drop_index("ix_weekly_settlement_member_id", table_name="weekly_settlement")
    op.drop_table("weekly_settlement")
