"""add missing indexes and unique constraints

Revision ID: 004_review
Revises: 003
"""
from alembic import op

revision = "004_review"
down_revision = "003_phase5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # mastery_record: composite unique + indexes
    op.create_unique_constraint("uk_member_word", "mastery_record", ["member_id", "word_id"])
    op.create_index("ix_mastery_member", "mastery_record", ["member_id"])
    op.create_index("ix_mastery_word", "mastery_record", ["word_id"])

    # word: index on unit_id for IN queries
    op.create_index("ix_word_unit", "word", ["unit_id"])

    # practice_session: index on member + started_at for stats
    op.create_index("ix_practice_member_date", "practice_session", ["member_id", "started_at"])

    # daily_task: index on plan_id for range queries
    op.create_index("ix_daily_task_plan", "daily_task", ["plan_id"])

    # plan_units: reverse index on unit_id
    op.create_index("ix_plan_units_unit", "plan_units", ["unit_id"])


def downgrade() -> None:
    op.drop_index("ix_plan_units_unit", table_name="plan_units")
    op.drop_index("ix_daily_task_plan", table_name="daily_task")
    op.drop_index("ix_practice_member_date", table_name="practice_session")
    op.drop_index("ix_word_unit", table_name="word")
    op.drop_index("ix_mastery_word", table_name="mastery_record")
    op.drop_index("ix_mastery_member", table_name="mastery_record")
    op.drop_constraint("uk_member_word", "mastery_record", type_="unique")
