"""word rich fields

Revision ID: 014_word_rich_fields
Revises: 013_record_created_at_idx
Create Date: 2026-07-23

为 word 表补充富字段 phonetic / definition / pos / example，
让词条从「英中对译」升级为可学的语言单位（音标 / 英文释义 / 词性 / 例句）。
全部 nullable，旧数据无需回填即可工作；ECDICT 导入与 AI 解析按可用性填充。

注：revision id 控制在 32 字符内以适配 alembic_version.version_num (VARCHAR(32))。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014_word_rich_fields"
down_revision: Union[str, None] = "013_record_created_at_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("word", sa.Column("phonetic", sa.String(length=200), nullable=True))
    op.add_column("word", sa.Column("definition", sa.String(length=1000), nullable=True))
    op.add_column("word", sa.Column("pos", sa.String(length=100), nullable=True))
    op.add_column("word", sa.Column("example", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("word", "example")
    op.drop_column("word", "pos")
    op.drop_column("word", "definition")
    op.drop_column("word", "phonetic")
