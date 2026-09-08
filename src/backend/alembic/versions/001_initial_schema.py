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


def upgrade() -> None:
    # Ensure postgis extension exists
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("format", sa.String(32), nullable=False),
        sa.Column("file_hash", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ingestion_jobs_file_hash", "ingestion_jobs", ["file_hash"])

    # Property objects
    op.create_table(
        "property_objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("property_objects.id"), nullable=True),
        sa.Column("three_d_property_id", sa.String(64), unique=True, nullable=False),
        sa.Column("geometry", geoalchemy2.Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True),
        sa.Column("z_min", sa.Float(), nullable=True),
        sa.Column("z_max", sa.Float(), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="SYNTHETIC"),
        sa.Column("source_list", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("property_objects.id"), nullable=True),
    )
    op.create_index("ix_property_objects_3d_id", "property_objects", ["three_d_property_id"])
    op.create_index("ix_property_objects_type", "property_objects", ["type"])
    op.create_index("ix_property_objects_status", "property_objects", ["status"])

    # Evidence
    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("property_object_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("property_objects.id"), nullable=True),
        sa.Column("evidence_type", sa.String(64), nullable=False),
        sa.Column("file_reference", sa.Text(), nullable=True),
        sa.Column("file_hash", sa.String(128), nullable=True),
        sa.Column("original_crs", sa.String(32), nullable=True),
        sa.Column("original_format", sa.String(32), nullable=True),
        sa.Column("source_system", sa.String(128), nullable=True),
        sa.Column("operator_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("ingestion_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_jobs.id"), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Source observations
    op.create_table(
        "source_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("property_object_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("property_objects.id"), nullable=False),
        sa.Column("attribute_name", sa.String(128), nullable=False),
        sa.Column("observed_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_id", sa.String(256), nullable=True),
        sa.Column("ingestion_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_jobs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Conflicts
    op.create_table(
        "conflicts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("property_object_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("property_objects.id"), nullable=False),
        sa.Column("rule_code", sa.String(16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="ERROR"),
        sa.Column("status", sa.String(16), nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    # Change events (immutable history)
    op.create_table(
        "change_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("property_object_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("property_objects.id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("old_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evidence.id"), nullable=True),
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
