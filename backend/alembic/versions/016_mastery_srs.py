"""mastery srs fields

Revision ID: 016_mastery_srs
Revises: 015_streak_xp_badges
Create Date: 2026-07-24

为 mastery_record 补 SM-2 间隔重复字段：interval_days / ease_factor /
last_reviewed_at / next_review_date。level 不再由计数阈值写入，改由
interval_days 派生（见 app/srs.py）。

回填采用「按 level 分档 + 到期日随机抖动分散」，避免同 level 词全部堆到同一天
到期（首日 due 雪崩）。无 mastery 行的新词不建行、不计 due_today（查询侧 INNER JOIN）。

注：revision id ≤32 字符适配 alembic_version.version_num (VARCHAR(32))。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "016_mastery_srs"
down_revision: Union[str, None] = "015_streak_xp_badges"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOT NULL 列带 server_default，ADD COLUMN 时 MariaDB 自动给现有行赋默认值
    op.add_column("mastery_record",
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("mastery_record",
        sa.Column("ease_factor", sa.Float(), nullable=False, server_default="2.5"))
    op.add_column("mastery_record",
        sa.Column("last_reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("mastery_record",
        sa.Column("next_review_date", sa.Date(), nullable=True))

    # 回填已练过的词（有 mastery 行）：按 level 分档 interval，到期日随机抖动分散防雪崩
    op.execute("""
        UPDATE mastery_record SET
          last_reviewed_at = updated_at,
          interval_days = CASE level
            WHEN 'learning'  THEN 1
            WHEN 'familiar'  THEN 3
            WHEN 'permanent' THEN 30
            ELSE 0
          END,
          next_review_date = CASE level
            WHEN 'learning'  THEN DATE_ADD(CURDATE(), INTERVAL FLOOR(RAND()*2) DAY)
            WHEN 'familiar'  THEN DATE_ADD(CURDATE(), INTERVAL 1 + FLOOR(RAND()*7) DAY)
            WHEN 'permanent' THEN DATE_ADD(CURDATE(), INTERVAL 30 + FLOOR(RAND()*31) DAY)
            ELSE CURDATE()
          END
    """)

    # 到期查询高频：复合索引 (member_id, next_review_date)
    op.create_index("ix_mastery_member_due", "mastery_record", ["member_id", "next_review_date"])


def downgrade() -> None:
    op.drop_index("ix_mastery_member_due", table_name="mastery_record")
    op.drop_column("mastery_record", "next_review_date")
    op.drop_column("mastery_record", "last_reviewed_at")
    op.drop_column("mastery_record", "ease_factor")
    op.drop_column("mastery_record", "interval_days")
