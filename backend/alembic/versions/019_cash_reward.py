"""cash reward

Revision ID: 019_cash_reward
Revises: 018_plan_rebalanced
Create Date: 2026-07-27

现金激励（Cash Incentive）数据层：
- member.cash_balance：虚拟钱包累计额（周学习现金 + 里程碑奖金累加进此）。
- weekly_settlement.cash_reward / cash_tier_label：本周学习现金 + 命中档位标签。
- cash_milestone 表：里程碑发放幂等台账（uq_member_milestone_key 防重发）。

防通胀：周现金与 bonus_xp 同 savepoint 原子发放；里程碑 snapshot 语义不回扣。
id/member_id 用 BigInteger 以匹配 member.id（bigint），否则 MariaDB errno 150
（见 015/017 迁移同类注释）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "019_cash_reward"
down_revision: Union[str, None] = "018_plan_rebalanced"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # member 虚拟钱包
    op.add_column(
        "member",
        sa.Column("cash_balance", sa.Float(), nullable=False, server_default="0.0"),
    )
    # weekly_settlement 周现金 + 档位标签
    op.add_column(
        "weekly_settlement",
        sa.Column("cash_reward", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "weekly_settlement",
        sa.Column("cash_tier_label", sa.String(length=40), nullable=True),
    )
    # cash_milestone 幂等台账
    op.create_table(
        "cash_milestone",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("member_id", sa.BigInteger(),
                  sa.ForeignKey("member.id", ondelete="CASCADE"), nullable=False),
        sa.Column("milestone_key", sa.String(length=80), nullable=False),
        sa.Column("milestone_type", sa.String(length=40), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("granted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("member_id", "milestone_key", name="uq_member_milestone_key"),
    )
    op.create_index("ix_cash_milestone_member_id", "cash_milestone", ["member_id"])


def downgrade() -> None:
    op.drop_index("ix_cash_milestone_member_id", table_name="cash_milestone")
    op.drop_table("cash_milestone")
    op.drop_column("weekly_settlement", "cash_tier_label")
    op.drop_column("weekly_settlement", "cash_reward")
    op.drop_column("member", "cash_balance")
