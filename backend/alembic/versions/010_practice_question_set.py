"""practice_session question_word_ids

Revision ID: 010_practice_question_set
Revises: 009_wrong_word_book
Create Date: 2026-07-08

practice_session 增 question_word_ids（JSON）：
- start_practice 时存本次题集的 word_id 列表
- submit_answer 校验 word_id 必须属于本会话题集，防提交任意词刷分
- nullable：旧会话为 NULL，提交时跳过校验（向后兼容）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010_practice_question_set"
down_revision: Union[str, None] = "009_wrong_word_book"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "practice_session",
        sa.Column("question_word_ids", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("practice_session", "question_word_ids")
