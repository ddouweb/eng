"""streak xp badges

Revision ID: 015_streak_xp_badges
Revises: 014_word_rich_fields
Create Date: 2026-07-23

坚持机制（游戏化）的数据基础：
- member_streak：持久化每个成员的连续学习状态（current/longest/freeze_balance/
  last_active_date），替代原先每次聚合计算；这样才能支持 freeze（补断签）、
  最长记录、月度发放等有状态能力。
- member_badges：徽章发放记录（member × badge_key 唯一，幂等）。
- member.total_xp：累计 XP（答对加分），驱动段位。

注：revision id 控制在 32 字符内以适配 alembic_version.version_num (VARCHAR(32))。
外键 member_id 用 BigInteger 以匹配 member.id（本项目主键实际为 bigint，否则
MariaDB 报 errno 150 "Foreign key constraint is incorrectly formed"）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015_streak_xp_badges"
down_revision: Union[str, None] = "014_word_rich_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "member_streak",
        sa.Column("member_id", sa.BigInteger(),
                  sa.ForeignKey("member.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("freeze_balance", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("last_active_date", sa.Date(), nullable=True),
        sa.Column("freeze_grant_month", sa.String(length=7), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "member_badges",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("member_id", sa.BigInteger(),
                  sa.ForeignKey("member.id", ondelete="CASCADE"), nullable=False),
        sa.Column("badge_key", sa.String(length=50), nullable=False),
        sa.Column("awarded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("member_id", "badge_key", name="uq_member_badge"),
    )
    op.add_column("member", sa.Column("total_xp", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("member", "total_xp")
    op.drop_table("member_badges")
    op.drop_table("member_streak")
