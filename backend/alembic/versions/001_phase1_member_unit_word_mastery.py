"""phase1_member_unit_word_mastery

Revision ID: 001
Revises:
Create Date: 2026-06-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- member ---
    op.create_table(
        "member",
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("avatar", sa.String(255), nullable=True),
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
    )

    # --- unit ---
    op.create_table(
        "unit",
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=True),
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
        sa.UniqueConstraint("sequence"),
    )

    # --- word ---
    op.create_table(
        "word",
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("unit_id", sa.BIGINT(), nullable=False),
        sa.Column("english", sa.String(500), nullable=False),
        sa.Column("chinese", sa.String(500), nullable=False),
        sa.Column(
            "type",
            sa.Enum("word", "sentence", name="wordtype"),
            nullable=False,
            server_default="word",
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
        sa.ForeignKeyConstraint(["unit_id"], ["unit.id"], ondelete="CASCADE"),
    )

    # --- mastery_record ---
    op.create_table(
        "mastery_record",
        sa.Column("id", sa.BIGINT(), autoincrement=True, nullable=False),
        sa.Column("member_id", sa.BIGINT(), nullable=False),
        sa.Column("word_id", sa.BIGINT(), nullable=False),
        sa.Column(
            "level",
            sa.Enum(
                "unlearned", "learning", "familiar", "permanent", name="masterylevel"
            ),
            nullable=False,
            server_default="unlearned",
        ),
        sa.Column("consecutive_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wrong_count", sa.Integer(), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["word_id"], ["word.id"], ondelete="CASCADE"),
    )

    # --- word_tags ---
    op.create_table(
        "word_tags",
        sa.Column("word_id", sa.BIGINT(), nullable=False),
        sa.Column(
            "tag",
            sa.Enum(
                "favorite",
                "high_freq",
                "exam_focus",
                "excluded",
                "memorized",
                name="tagtype",
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("word_id", "tag"),
        sa.ForeignKeyConstraint(["word_id"], ["word.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("word_tags")
    op.drop_table("mastery_record")
    op.drop_table("word")
    op.drop_table("unit")
    op.drop_table("member")
