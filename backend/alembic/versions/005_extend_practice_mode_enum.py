"""extend_practice_mode_enum

Revision ID: 005_extend_practice_mode_enum
Revises: 004_review
Create Date: 2026-06-16

把 practice_session.mode 的 MySQL ENUM 扩展到 PracticeMode Python 枚举的全部 12 个值。
原迁移 002 只放了 5 个值，后续新增的 cn2en_choice / en2cn_write / matching /
timed_challenge / scramble / memory_flash / flip_match 没有 ALTER 同步，
导致这些模式在 start_practice 时插入失败、返回 500。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005_extend_practice_mode_enum"
down_revision: Union[str, None] = "004_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 必须与 backend/app/models/enums.py 的 PracticeMode 顺序保持一致
_FULL_MODES = (
    "flashcard",
    "spelling",
    "choice",
    "cn2en_choice",
    "en2cn_write",
    "dictation",
    "matching",
    "timed_challenge",
    "scramble",
    "memory_flash",
    "flip_match",
    "dialogue",
)


def upgrade() -> None:
    # MySQL 用 ALTER MODIFY 改 ENUM 取值集合，原生 SQL 最稳。
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        values_sql = ", ".join(f"'{m}'" for m in _FULL_MODES)
        op.execute(
            f"ALTER TABLE practice_session "
            f"MODIFY COLUMN mode ENUM({values_sql}) NOT NULL"
        )
    else:
        # SQLite 等其它后端用 SQLAlchemy 抽象
        op.alter_column(
            "practice_session",
            "mode",
            existing_type=sa.Enum(*_FULL_MODES, name="practicemode"),
            type_=sa.Enum(*_FULL_MODES, name="practicemode"),
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    _OLD_MODES = ("flashcard", "spelling", "choice", "dictation", "dialogue")
    if bind.dialect.name == "mysql":
        values_sql = ", ".join(f"'{m}'" for m in _OLD_MODES)
        op.execute(
            f"ALTER TABLE practice_session "
            f"MODIFY COLUMN mode ENUM({values_sql}) NOT NULL"
        )
    else:
        op.alter_column(
            "practice_session",
            "mode",
            existing_type=sa.Enum(*_FULL_MODES, name="practicemode"),
            type_=sa.Enum(*_OLD_MODES, name="practicemode"),
            existing_nullable=False,
        )
