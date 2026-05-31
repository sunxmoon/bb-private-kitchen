"""add missing indexes for query performance

Revision ID: 003
Revises: 002
Create Date: 2026-05-30
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # audit_logs.timestamp — used by get_audit_logs() ORDER BY DESC
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])

    # orders.created_at — used by get_order_history() ORDER BY DESC
    op.create_index("ix_orders_created_at", "orders", ["created_at"])

    # dishes.category — used by get_dish_categories() DISTINCT and search_dishes() filter
    op.create_index("ix_dishes_category", "dishes", ["category"])

    # dishes.name — used by search_dishes() ILIKE (partial help for left-anchored searches)
    op.create_index("ix_dishes_name", "dishes", ["name"])

    # orders.status — used by get_current_order() filter (already has index, add composite)
    op.create_index("ix_orders_status_created_at", "orders", ["status", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_orders_status_created_at")
    op.drop_index("ix_dishes_name")
    op.drop_index("ix_dishes_category")
    op.drop_index("ix_orders_created_at")
    op.drop_index("ix_audit_logs_timestamp")
