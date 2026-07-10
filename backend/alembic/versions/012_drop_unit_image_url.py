"""drop_unit_image_url

Revision ID: 012_drop_unit_image_url
Revises: 011_mastery_unique
Create Date: 2026-07-09

删除 unit 表已废弃的 image_url 列。

背景：该列由 001 创建，原计划由一个 revision="002" 的迁移删除，但那个迁移与
002_phase3_practice_session_record 撞了 revision id "002"，形成孤儿分支且从未被执行，
导致 alembic 出现 "Revision 002 is present more than once" 与 multiple heads。
本迁移把"删除 image_url"重挂到主线（011 之后）执行，同时消除上述问题。
unit 模型与全部业务代码均已不引用 image_url，删除安全。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012_drop_unit_image_url"
down_revision: Union[str, None] = "011_mastery_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("unit", "image_url")


def downgrade() -> None:
    op.add_column("unit", sa.Column("image_url", sa.String(500), nullable=True))
