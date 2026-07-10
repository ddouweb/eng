"""practice_record created_at index

Revision ID: 013_record_created_at_idx
Revises: 012_drop_unit_image_url
Create Date: 2026-07-09

为 practice_record.created_at 建索引。
周复习/月复习选题（get_word_ids_between）与首次判定（_classify_attempt）
都按 created_at 区间过滤，原先无索引且 func.DATE() 包裹也无法命中；
代码已改为区间比较，本迁移补上索引使其走范围扫描。

注：revision id 控制在 32 字符内以适配 alembic_version.version_num (VARCHAR(32))。
"""
from typing import Sequence, Union

from alembic import op


revision: str = "013_record_created_at_idx"
down_revision: Union[str, None] = "012_drop_unit_image_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_practice_record_created_at", "practice_record", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_practice_record_created_at", table_name="practice_record")
