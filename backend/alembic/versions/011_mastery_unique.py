"""mastery_record unique (member_id, word_id)

Revision ID: 011_mastery_unique
Revises: 010_practice_question_set
Create Date: 2026-07-08

为 mastery_record 增加 (member_id, word_id) 联合唯一约束：
- 并发 get_or_create 不再产生重复行（mastery_repo 已用 SAVEPOINT 捕获
  IntegrityError 回读已有记录）
- 修复下游 stats 计数虚增、practice_service mastery_map 任意取一条的问题

加约束前先去重：同 (member_id, word_id) 的历史重复行只保留 id 最大的一条。
（重复行是历史 race 产物；保留最新一条即可，其计数已是该词最新状态。）
"""
from typing import Sequence, Union

from alembic import op


revision: str = "011_mastery_unique"
down_revision: Union[str, None] = "010_practice_question_set"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 去重：同 (member_id, word_id) 仅保留 id 最大的一条（删掉 id 较小的重复行）
    op.execute(
        """
        DELETE m1 FROM mastery_record m1
        INNER JOIN mastery_record m2
          ON m1.member_id = m2.member_id
         AND m1.word_id = m2.word_id
         AND m1.id < m2.id
        """
    )
    op.create_unique_constraint(
        "uk_member_word_mastery", "mastery_record", ["member_id", "word_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uk_member_word_mastery", "mastery_record", type_="unique")
