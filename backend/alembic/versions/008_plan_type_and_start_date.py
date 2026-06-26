"""plan_type_and_start_date

Revision ID: 008_plan_type_and_start_date
Revises: 007_plan_review_tasks
Create Date: 2026-06-26

为二三轮计划做准备：
- learning_plan 新增 start_date（计划生效起始日，默认今天）
- learning_plan 新增 plan_type ENUM('forward','review_only','wrong_word_drill')，默认 'forward'
- daily_task.task_type ENUM 追加 'wrong_word_drill'
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008_plan_type_and_start_date"
down_revision: Union[str, None] = "007_plan_review_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PLAN_TYPES = ("forward", "review_only", "wrong_word_drill")
_TASK_TYPES_NEW = ("learn", "weekly_review", "monthly_review", "wrong_word_drill")


def upgrade() -> None:
    bind = op.get_bind()

    # 1) learning_plan.start_date
    if bind.dialect.name == "mysql":
        op.execute(
            "ALTER TABLE learning_plan "
            "ADD COLUMN start_date DATE NOT NULL DEFAULT (CURRENT_DATE) AFTER deadline"
        )
    else:
        op.add_column(
            "learning_plan",
            sa.Column(
                "start_date",
                sa.Date(),
                nullable=False,
                server_default=sa.func.current_date(),
            ),
        )

    # 2) learning_plan.plan_type
    if bind.dialect.name == "mysql":
        values_sql = ", ".join(f"'{t}'" for t in _PLAN_TYPES)
        op.execute(
            f"ALTER TABLE learning_plan "
            f"ADD COLUMN plan_type ENUM({values_sql}) NOT NULL DEFAULT 'forward' "
            f"AFTER monthly_review_day"
        )
    else:
        op.add_column(
            "learning_plan",
            sa.Column(
                "plan_type",
                sa.String(length=32),
                nullable=False,
                server_default="forward",
            ),
        )

    # 3) daily_task.task_type 追加 'wrong_word_drill'
    if bind.dialect.name == "mysql":
        values_sql = ", ".join(f"'{t}'" for t in _TASK_TYPES_NEW)
        op.execute(
            f"ALTER TABLE daily_task "
            f"MODIFY COLUMN task_type ENUM({values_sql}) NOT NULL DEFAULT 'learn'"
        )
    else:
        # SQLite 等用 String，无需修改
        pass


def downgrade() -> None:
    bind = op.get_bind()

    # 回退 task_type
    if bind.dialect.name == "mysql":
        old_values = ", ".join(f"'{t}'" for t in _TASK_TYPES_NEW[:3])
        # 先把 wrong_word_drill 数据改成 learn（如有）
        op.execute("UPDATE daily_task SET task_type='learn' WHERE task_type='wrong_word_drill'")
        op.execute(
            f"ALTER TABLE daily_task "
            f"MODIFY COLUMN task_type ENUM({old_values}) NOT NULL DEFAULT 'learn'"
        )

    op.drop_column("learning_plan", "plan_type")
    op.drop_column("learning_plan", "start_date")
