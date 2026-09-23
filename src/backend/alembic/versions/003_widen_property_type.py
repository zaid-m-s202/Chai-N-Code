"""Widen property_objects.type to VARCHAR(32) for subterranean infrastructure types.

Revision ID: 003_widen_property_type
Revises: 002_production_schema_update
Create Date: 2026-09-23 14:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_widen_property_type"
down_revision: Union[str, None] = "002_production_schema_update"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "property_objects",
        "type",
        existing_type=sa.String(16),
        type_=sa.String(32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "property_objects",
        "type",
        existing_type=sa.String(32),
        type_=sa.String(16),
        existing_nullable=False,
    )
