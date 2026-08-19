"""lottery scratch card

Revision ID: 020_lottery
Revises: 019_cash_reward
Create Date: 2026-08-19

彩票抽卡奖励机制数据层：
- member.lottery_wealth：彩金余额（刮刮乐中奖累计，与 cash_balance 现金激励完全分开）。
- lottery_grant 表：抽卡次数发放台账（8 类学习行为 + init 补偿，uq_member_lottery_grant 防重发）。
- lottery_ticket 表：出票 = 次数消耗记录（后端开奖存全量票面 JSON；batch_id 支持开一批玩法；
  settled_at NULL = 未结算）。

可用次数 = SUM(lottery_grant.draws) - COUNT(lottery_ticket)，两台账对账，member 不存次数。
id/member_id 用 BigInteger 以匹配 member.id（bigint），否则 MariaDB errno 150
（见 015/017/019 迁移同类注释）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "020_lottery"
down_revision: Union[str, None] = "019_cash_reward"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # member 彩金余额
    op.add_column(
        "member",
        sa.Column("lottery_wealth", sa.Float(), nullable=False, server_default="0.0"),
    )
    # 抽卡次数发放台账
    op.create_table(
        "lottery_grant",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("member_id", sa.BigInteger(),
                  sa.ForeignKey("member.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("grant_key", sa.String(length=80), nullable=False),
        sa.Column("draws", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("remark", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("member_id", "grant_key", name="uq_member_lottery_grant"),
    )
    op.create_index("ix_lottery_grant_member_id", "lottery_grant", ["member_id"])
    # 出票记录
    op.create_table(
        "lottery_ticket",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("member_id", sa.BigInteger(),
                  sa.ForeignKey("member.id", ondelete="CASCADE"), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=True),
        sa.Column("prize", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ticket", sa.JSON(), nullable=False),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lottery_ticket_member_id", "lottery_ticket", ["member_id"])
    op.create_index("ix_lottery_ticket_batch_id", "lottery_ticket", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_lottery_ticket_batch_id", table_name="lottery_ticket")
    op.drop_index("ix_lottery_ticket_member_id", table_name="lottery_ticket")
    op.drop_table("lottery_ticket")
    op.drop_index("ix_lottery_grant_member_id", table_name="lottery_grant")
    op.drop_table("lottery_grant")
    op.drop_column("member", "lottery_wealth")
