"""remove_unit_image_url

Revision ID: 002
Revises: 001
Create Date: 2026-06-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("unit", "image_url")


def downgrade() -> None:
    op.add_column("unit", sa.Column("image_url", sa.String(500), nullable=True))
