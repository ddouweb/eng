"""word_seq

Revision ID: 006_word_seq
Revises: 005_extend_practice_mode_enum
Create Date: 2026-06-19

给 word 表增加 seq（序号）列，用于记录词条在教材单元内的印刷序号（NO）。
可空、不唯一：单元内序号可能重复（如 U13 NO21 印刷重复），手动添加的旧词也可能无序号。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006_word_seq"
down_revision: Union[str, None] = "005_extend_practice_mode_enum"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("word", sa.Column("seq", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("word", "seq")
