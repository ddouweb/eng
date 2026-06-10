"""phase3_practice_session_record

Revision ID: 002
Revises: 001
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- practice_session ---
    op.create_table(
        "practice_session",
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.BIGINT(), nullable=False),
        sa.Column(
            "mode",
            sa.Enum(
                "flashcard", "spelling", "choice", "dictation", "dialogue",
                name="practicemode",
            ),
            nullable=False,
        ),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "started_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
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
    op.create_index("ix_practice_session_member_id", "practice_session", ["member_id"])
    op.create_index("ix_practice_session_started_at", "practice_session", ["started_at"])

    # --- practice_record ---
    op.create_table(
        "practice_record",
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.BIGINT(), nullable=False),
        sa.Column("word_id", sa.BIGINT(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("user_answer", sa.String(500), nullable=True),
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
        sa.ForeignKeyConstraint(["session_id"], ["practice_session.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["word_id"], ["word.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_practice_record_session_id", "practice_record", ["session_id"])
    op.create_index("ix_practice_record_word_id", "practice_record", ["word_id"])


def downgrade() -> None:
    op.drop_index("ix_practice_record_word_id", table_name="practice_record")
    op.drop_index("ix_practice_record_session_id", table_name="practice_record")
    op.drop_table("practice_record")

    op.drop_index("ix_practice_session_started_at", table_name="practice_session")
    op.drop_index("ix_practice_session_member_id", table_name="practice_session")
    op.drop_table("practice_session")
