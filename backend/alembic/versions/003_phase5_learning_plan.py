"""phase5_learning_plan

Revision ID: 003
Revises: 002
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- learning_plan ---
    op.create_table(
        "learning_plan",
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.BIGINT(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("daily_goal", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "completed", "paused", name="planstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["member_id"], ["member.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_learning_plan_member_id", "learning_plan", ["member_id"])
    op.create_index("ix_learning_plan_status", "learning_plan", ["status"])

    # --- plan_units ---
    op.create_table(
        "plan_units",
        sa.Column("plan_id", sa.BIGINT(), nullable=False),
        sa.Column("unit_id", sa.BIGINT(), nullable=False),
        sa.PrimaryKeyConstraint("plan_id", "unit_id"),
        sa.ForeignKeyConstraint(["plan_id"], ["learning_plan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["unit.id"], ondelete="CASCADE"),
    )

    # --- daily_task ---
    op.create_table(
        "daily_task",
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.BIGINT(), nullable=False),
        sa.Column("task_date", sa.Date(), nullable=False),
        sa.Column("new_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_review", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            sa.Enum("pending", "in_progress", "completed", "skipped", name="taskstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["plan_id"], ["learning_plan.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("plan_id", "task_date", name="uk_plan_date"),
    )


def downgrade() -> None:
    op.drop_table("daily_task")
    op.drop_table("plan_units")
    op.drop_index("ix_learning_plan_status", table_name="learning_plan")
    op.drop_index("ix_learning_plan_member_id", table_name="learning_plan")
    op.drop_table("learning_plan")
