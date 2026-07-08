"""wrong_word_book

Revision ID: 009_wrong_word_book
Revises: 008_plan_type_and_start_date
Create Date: 2026-07-08

新增错题本表 wrong_word_book：
- (member_id, word_id) 联合唯一约束（upsert 依赖，保证同一 member 同一 word 只有一条记录）
- member_id / word_id 单列索引（列表分页、按 word 删除、计数）
- FK ondelete=CASCADE，删 member / word 时自动清理
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009_wrong_word_book"
down_revision: Union[str, None] = "008_plan_type_and_start_date"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 用 raw SQL：MariaDB 不接受 alembic 生成的 COLLATION=... 语法，
    # 且现有 member/word 表为 utf8mb4_unicode_ci，新建表必须 collation 一致，
    # 否则 FK 创建报 errno 150 "Foreign key constraint is incorrectly formed"
    op.execute(
        """
        CREATE TABLE wrong_word_book (
            id BIGINT NOT NULL AUTO_INCREMENT,
            member_id BIGINT NOT NULL,
            word_id BIGINT NOT NULL,
            added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            wrong_count INT NOT NULL DEFAULT 1,
            PRIMARY KEY (id),
            CONSTRAINT fk_wrongbook_member FOREIGN KEY (member_id)
                REFERENCES member (id) ON DELETE CASCADE,
            CONSTRAINT fk_wrongbook_word FOREIGN KEY (word_id)
                REFERENCES word (id) ON DELETE CASCADE,
            CONSTRAINT uk_member_word_wrongbook UNIQUE (member_id, word_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    op.create_index("ix_wrongbook_member", "wrong_word_book", ["member_id"])
    op.create_index("ix_wrongbook_word", "wrong_word_book", ["word_id"])


def downgrade() -> None:
    # MariaDB 下 drop_index 会因 FK 占用索引失败，直接 drop_table 一步到位
    op.drop_table("wrong_word_book")
