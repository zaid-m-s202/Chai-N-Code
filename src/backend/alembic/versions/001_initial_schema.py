"""Initial schema for 3D Cadastral Intelligence.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-05 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Dialect-agnostic type definitions for PostgreSQL (native UUID/JSONB) and SQLite (UUID/JSON)
UUID_TYPE = sa.Uuid(as_uuid=True).with_variant(postgresql.UUID(as_uuid=True), "postgresql")
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()
    # Ensure postgis extension exists in PostgreSQL environments
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Users table
    op.create_table(
        "users",
        sa.Column("id", UUID_TYPE, primary_key=True),
        sa.Column("username", sa.String(128), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="PUBLIC_VIEWER"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"])

    # Ingestion jobs
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", UUID_TYPE, primary_key=True),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("format", sa.String(32), nullable=False),
        sa.Column("file_hash", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("operator_id", UUID_TYPE, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ingestion_jobs_file_hash", "ingestion_jobs", ["file_hash"])

    # Property objects
    op.create_table(
        "property_objects",
        sa.Column("id", UUID_TYPE, primary_key=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("parent_id", UUID_TYPE, sa.ForeignKey("property_objects.id"), nullable=True),
        sa.Column("three_d_property_id", sa.String(64), unique=True, nullable=False),
        sa.Column("geometry", geoalchemy2.Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True),
        sa.Column("z_min", sa.Float(), nullable=True),
        sa.Column("z_max", sa.Float(), nullable=True),
        sa.Column("attributes", JSON_TYPE, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="SYNTHETIC"),
        sa.Column("source_list", JSON_TYPE, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", UUID_TYPE, sa.ForeignKey("property_objects.id"), nullable=True),
    )
    op.create_index("ix_property_objects_3d_id", "property_objects", ["three_d_property_id"])
    op.create_index("ix_property_objects_type", "property_objects", ["type"])
    op.create_index("ix_property_objects_status", "property_objects", ["status"])

    # Evidence
    op.create_table(
        "evidence",
        sa.Column("id", UUID_TYPE, primary_key=True),
        sa.Column("property_object_id", UUID_TYPE, sa.ForeignKey("property_objects.id"), nullable=True),
        sa.Column("evidence_type", sa.String(64), nullable=False),
        sa.Column("file_reference", sa.Text(), nullable=True),
        sa.Column("file_hash", sa.String(128), nullable=True),
        sa.Column("original_crs", sa.String(32), nullable=True),
        sa.Column("original_format", sa.String(32), nullable=True),
        sa.Column("source_system", sa.String(128), nullable=True),
        sa.Column("operator_id", UUID_TYPE, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("ingestion_job_id", UUID_TYPE, sa.ForeignKey("ingestion_jobs.id"), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Source observations
    op.create_table(
        "source_observations",
        sa.Column("id", UUID_TYPE, primary_key=True),
        sa.Column("property_object_id", UUID_TYPE, sa.ForeignKey("property_objects.id"), nullable=False),
        sa.Column("attribute_name", sa.String(128), nullable=False),
        sa.Column("observed_value", JSON_TYPE, nullable=False),
        sa.Column("source_confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_id", sa.String(256), nullable=True),
        sa.Column("ingestion_job_id", UUID_TYPE, sa.ForeignKey("ingestion_jobs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Conflicts
    op.create_table(
        "conflicts",
        sa.Column("id", UUID_TYPE, primary_key=True),
        sa.Column("property_object_id", UUID_TYPE, sa.ForeignKey("property_objects.id"), nullable=False),
        sa.Column("rule_code", sa.String(16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="ERROR"),
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", UUID_TYPE, sa.ForeignKey("users.id"), nullable=True),
    )

    # Change events (immutable history)
    op.create_table(
        "change_events",
        sa.Column("id", UUID_TYPE, primary_key=True),
        sa.Column("property_object_id", UUID_TYPE, sa.ForeignKey("property_objects.id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("old_state", JSON_TYPE, nullable=True),
        sa.Column("new_state", JSON_TYPE, nullable=True),
        sa.Column("actor_id", UUID_TYPE, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("evidence_id", UUID_TYPE, sa.ForeignKey("evidence.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("change_events")
    op.drop_table("conflicts")
    op.drop_table("source_observations")
    op.drop_table("evidence")
    op.drop_table("property_objects")
    op.drop_table("ingestion_jobs")
    op.drop_table("users")
