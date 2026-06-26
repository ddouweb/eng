"""plan_review_tasks

Revision ID: 007_plan_review_tasks
Revises: 006_word_seq
Create Date: 2026-06-26

为方案 B（周复习 / 月复习任务）做schema 准备：
- daily_task 新增 task_type 列（learn/weekly_review/monthly_review）
- learning_plan 新增 learn_weekdays（JSON 字符串，如 "[0,1,2,3,4]"）和 monthly_review_day（None/1-28/31）
- daily_task 唯一约束从 (plan_id, task_date) 改为 (plan_id, task_date, task_type)
- 新增索引 ix_daily_task_type
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007_plan_review_tasks"
down_revision: Union[str, None] = "006_word_seq"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TASK_TYPES = ("learn", "weekly_review", "monthly_review")


def upgrade() -> None:
    bind = op.get_bind()

    # 1) daily_task.task_type
    if bind.dialect.name == "mysql":
        values_sql = ", ".join(f"'{t}'" for t in _TASK_TYPES)
        op.execute(
            f"ALTER TABLE daily_task "
            f"ADD COLUMN task_type ENUM({values_sql}) NOT NULL DEFAULT 'learn' AFTER status"
        )
    else:
        op.add_column(
            "daily_task",
            sa.Column(
                "task_type",
                sa.String(length=32),
                nullable=False,
                server_default="learn",
            ),
        )

    # 2) learning_plan 新字段
    op.add_column(
        "learning_plan",
        sa.Column(
            "learn_weekdays",
            sa.String(length=64),
            nullable=False,
            server_default="[0,1,2,3,4]",
        ),
    )
    op.add_column(
        "learning_plan",
        sa.Column("monthly_review_day", sa.Integer(), nullable=True),
    )

    # 3) 改唯一约束：兼容已有数据，再换新约束
    if bind.dialect.name == "mysql":
        op.drop_constraint("uk_plan_date", "daily_task", type_="unique")
    else:
        op.drop_constraint("uk_plan_date", "daily_task", type_="unique")
    op.create_unique_constraint(
        "uk_plan_date_type", "daily_task", ["plan_id", "task_date", "task_type"]
    )

    # 4) 索引
    op.create_index("ix_daily_task_type", "daily_task", ["task_type"])


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("ix_daily_task_type", table_name="daily_task")
    op.drop_constraint("uk_plan_date_type", "daily_task", type_="unique")
    op.create_unique_constraint("uk_plan_date", "daily_task", ["plan_id", "task_date"])

    op.drop_column("learning_plan", "monthly_review_day")
    op.drop_column("learning_plan", "learn_weekdays")

    if bind.dialect.name == "mysql":
        op.execute("ALTER TABLE daily_task DROP COLUMN task_type")
    else:
        op.drop_column("daily_task", "task_type")
