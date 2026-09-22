"""Production schema update: property_records table, property_objects extensions, and indexes.

Revision ID: 002_production_schema_update
Revises: 001_initial_schema
Create Date: 2026-09-23 01:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_production_schema_update"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID_TYPE = sa.Uuid(as_uuid=True).with_variant(postgresql.UUID(as_uuid=True), "postgresql")
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Extend property_objects with ULPIN, stratum, volume_m3
    op.add_column("property_objects", sa.Column("ulpin", sa.String(32), nullable=True))
    op.add_column("property_objects", sa.Column("stratum", sa.String(20), nullable=True, server_default="SURFACE"))
    op.add_column("property_objects", sa.Column("volume_m3", sa.Float(), nullable=True))

    # 2. Add B-Tree indexes on property_objects
    op.create_index("ix_property_objects_ulpin", "property_objects", ["ulpin"])
    op.create_index("ix_property_objects_stratum", "property_objects", ["stratum"])
    op.create_index("ix_property_objects_parent_id", "property_objects", ["parent_id"])
    op.create_index("ix_property_objects_superseded_by", "property_objects", ["superseded_by"])

    # 3. Add spatial GiST index on property_objects.geometry (PostgreSQL/PostGIS)
    if is_postgres:
        op.create_index("idx_property_objects_geometry", "property_objects", ["geometry"], postgresql_using="gist")

    # 4. Create property_records table for legal & land registry linkages
    op.create_table(
        "property_records",
        sa.Column("id", UUID_TYPE, primary_key=True),
        sa.Column("property_object_id", UUID_TYPE, sa.ForeignKey("property_objects.id"), nullable=False),
        sa.Column("three_d_property_id", sa.String(64), nullable=False),
        sa.Column("ulpin", sa.String(32), nullable=False),
        sa.Column("owner_party_id", sa.String(128), nullable=False),
        sa.Column("registration_number", sa.String(64), nullable=True),
        sa.Column("registration_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rights_type", sa.String(32), nullable=False, server_default="freehold"),
        sa.Column("encumbrances", JSON_TYPE, nullable=False, server_default="[]"),
        sa.Column("linkage_status", sa.String(16), nullable=False, server_default="LINKED"),
        sa.Column("source_system", sa.String(64), nullable=False, server_default="STATE_LAND_REGISTRY"),
        sa.Column("sync_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", UUID_TYPE, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_property_records_property_object_id", "property_records", ["property_object_id"])
    op.create_index("ix_property_records_three_d_property_id", "property_records", ["three_d_property_id"])
    op.create_index("ix_property_records_ulpin", "property_records", ["ulpin"])
    op.create_index("ix_property_records_linkage_status", "property_records", ["linkage_status"])
    op.create_index("ix_property_records_created_by", "property_records", ["created_by"])

    # 5. Add foreign key indexes on ingestion_jobs
    op.create_index("ix_ingestion_jobs_operator_id", "ingestion_jobs", ["operator_id"])

    # 6. Add foreign key indexes on evidence
    op.create_index("ix_evidence_property_object_id", "evidence", ["property_object_id"])
    op.create_index("ix_evidence_operator_id", "evidence", ["operator_id"])
    op.create_index("ix_evidence_ingestion_job_id", "evidence", ["ingestion_job_id"])

    # 7. Add foreign key indexes on source_observations
    op.create_index("ix_source_observations_property_object_id", "source_observations", ["property_object_id"])
    op.create_index("ix_source_observations_ingestion_job_id", "source_observations", ["ingestion_job_id"])

    # 8. Add foreign key indexes on conflicts
    op.create_index("ix_conflicts_property_object_id", "conflicts", ["property_object_id"])
    op.create_index("ix_conflicts_resolved_by", "conflicts", ["resolved_by"])

    # 9. Add foreign key indexes on change_events
    op.create_index("ix_change_events_property_object_id", "change_events", ["property_object_id"])
    op.create_index("ix_change_events_actor_id", "change_events", ["actor_id"])
    op.create_index("ix_change_events_evidence_id", "change_events", ["evidence_id"])


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Drop change_events indexes
    op.drop_index("ix_change_events_evidence_id", table_name="change_events")
    op.drop_index("ix_change_events_actor_id", table_name="change_events")
    op.drop_index("ix_change_events_property_object_id", table_name="change_events")

    # Drop conflicts indexes
    op.drop_index("ix_conflicts_resolved_by", table_name="conflicts")
    op.drop_index("ix_conflicts_property_object_id", table_name="conflicts")

    # Drop source_observations indexes
    op.drop_index("ix_source_observations_ingestion_job_id", table_name="source_observations")
    op.drop_index("ix_source_observations_property_object_id", table_name="source_observations")

    # Drop evidence indexes
    op.drop_index("ix_evidence_ingestion_job_id", table_name="evidence")
    op.drop_index("ix_evidence_operator_id", table_name="evidence")
    op.drop_index("ix_evidence_property_object_id", table_name="evidence")

    # Drop ingestion_jobs indexes
    op.drop_index("ix_ingestion_jobs_operator_id", table_name="ingestion_jobs")

    # Drop property_records table
    op.drop_table("property_records")

    # Drop property_objects spatial and btree indexes
    if is_postgres:
        op.drop_index("idx_property_objects_geometry", table_name="property_objects")
    op.drop_index("ix_property_objects_superseded_by", table_name="property_objects")
    op.drop_index("ix_property_objects_parent_id", table_name="property_objects")
    op.drop_index("ix_property_objects_stratum", table_name="property_objects")
    op.drop_index("ix_property_objects_ulpin", table_name="property_objects")

    # Drop added columns from property_objects
    op.drop_column("property_objects", "volume_m3")
    op.drop_column("property_objects", "stratum")
    op.drop_column("property_objects", "ulpin")
