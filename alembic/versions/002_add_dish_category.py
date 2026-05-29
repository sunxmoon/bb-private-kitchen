"""Add dish category field

Revision ID: 002
Revises: 001
Create Date: 2026-05-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dishes", sa.Column("category", sa.String(50), server_default=""))


def downgrade() -> None:
    op.drop_column("dishes", "category")
