"""Ingestion pipeline orchestrator.

Coordinates adapter selection, provenance recording, observation storage,
event sourcing, GIS normalization, multi-source fusion, and conflict detection.
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from geoalchemy2.shape import from_shape

from app.models.property_object import PropertyObject
from app.models.source_observation import SourceObservation
from app.models.evidence import Evidence
from app.models.change_event import ChangeEvent
from app.models.conflict import Conflict
from app.models.ingestion_job import IngestionJob
from app.ingestion.adapters.base import IngestionAdapter, CanonicalRecord
from app.ingestion.adapters.geojson_adapter import GeoJSONAdapter
from app.ingestion.adapters.csv_adapter import CSVAdapter
from app.services.id_generator import make_3d_property_id, parse_3d_property_id
from app.services.fusion import Observation as FusionObservation, fuse_attribute
from app.services.floor_height_heuristic import (
    estimate_building_levels,
    compute_unit_vertical_extent,
    get_typical_floor_height,
)


def get_adapter_for_format(file_format: str) -> IngestionAdapter:
    fmt = file_format.lower().strip()
    if fmt in ("geojson", "json"):
        return GeoJSONAdapter()
    elif fmt == "csv":
        return CSVAdapter()
    raise ValueError(f"Unsupported format: {file_format}. Supported formats in MVP: geojson, csv")


def process_ingestion(
    db: Session,
    job_id: UUID,
    filename: str,
    file_content: bytes,
    file_format: str,
    operator_id: Optional[UUID] = None,
    source_system: Optional[str] = None,
) -> IngestionJob:
    """Execute ingestion end-to-end, recording provenance, raw observations, and fusion."""
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        raise ValueError(f"Job {job_id} not found")

    job.status = "RUNNING"
    db.commit()

    try:
        file_hash = hashlib.sha256(file_content).hexdigest()
        job.file_hash = file_hash

        adapter = get_adapter_for_format(file_format)
        records: list[CanonicalRecord] = adapter.parse(
            file_content,
            filename,
            metadata={"source_system": source_system, "operator_id": str(operator_id) if operator_id else None},
        )

        created_count = 0

        for rec in records:
            # Generate immutable 3D Property ID: {ULPIN}-B{seq}-F{seq}-U{seq}
            three_d_id = make_3d_property_id(
                ulpin=rec.ulpin,
                building_seq=rec.building_seq,
                floor_seq=rec.floor_seq,
                unit_seq=rec.unit_seq,
            )

            # Check if property already exists
            prop = db.query(PropertyObject).filter(
                PropertyObject.three_d_property_id == three_d_id
            ).first()

            now = datetime.now(timezone.utc)
            geom_elem = None
            if rec.geometry is not None:
                try:
                    geom_elem = from_shape(rec.geometry, srid=4326)
                except Exception:
                    # In SQLite test environments without SpatiaLite, geoalchemy2 from_shape may be skipped
                    geom_elem = None

            evidence = Evidence(
                evidence_type=file_format.lower(),
                file_reference=filename,
                file_hash=file_hash,
                original_crs=rec.original_crs,
                original_format=file_format.lower(),
                source_system=source_system or "direct_upload",
                operator_id=operator_id,
                ingestion_job_id=job.id,
                captured_at=rec.observed_at or now,
            )
            db.add(evidence)
            db.flush()

            if not prop:
                # Vertical bound estimation using calibrated floor-height heuristic if missing
                z_min = rec.z_min
                z_max = rec.z_max
                use_type = rec.attributes.get("use") or rec.attributes.get("use_type")
                floor_count = rec.floor_count
                height = rec.height

                if rec.object_type == "unit" and (z_min is None or z_max is None):
                    floor_h = get_typical_floor_height(use_type)
                    calc_z_min, calc_z_max = compute_unit_vertical_extent(rec.floor_seq, floor_h, base_z=0.0)
                    z_min = z_min if z_min is not None else calc_z_min
                    z_max = z_max if z_max is not None else calc_z_max
                elif rec.object_type == "building":
                    eff_h, eff_fc, eff_fh = estimate_building_levels(height, floor_count, use_type=use_type)
                    if height is None:
                        height = eff_h
                    if floor_count is None:
                        floor_count = eff_fc
                    if z_max is None:
                        z_max = round((z_min or 0.0) + height, 2)

                # Parent hierarchy linking
                parent_id = None
                if rec.object_type == "building":
                    parcel = db.query(PropertyObject).filter(
                        PropertyObject.three_d_property_id == make_3d_property_id(rec.ulpin, 0, 0, 0),
                        PropertyObject.superseded_by.is_(None),
                    ).first()
                    if parcel:
                        parent_id = parcel.id
                elif rec.object_type == "floor":
                    bldg = db.query(PropertyObject).filter(
                        PropertyObject.three_d_property_id == make_3d_property_id(rec.ulpin, rec.building_seq, 0, 0),
                        PropertyObject.superseded_by.is_(None),
                    ).first()
                    if bldg:
                        parent_id = bldg.id
                elif rec.object_type == "unit":
                    floor_obj = db.query(PropertyObject).filter(
                        PropertyObject.three_d_property_id == make_3d_property_id(rec.ulpin, rec.building_seq, rec.floor_seq, 0),
                        PropertyObject.superseded_by.is_(None),
                    ).first()
                    if floor_obj:
                        parent_id = floor_obj.id
                    else:
                        bldg = db.query(PropertyObject).filter(
                            PropertyObject.three_d_property_id == make_3d_property_id(rec.ulpin, rec.building_seq, 0, 0),
                            PropertyObject.superseded_by.is_(None),
                        ).first()
                        if bldg:
                            parent_id = bldg.id

                # New property object: starts INFERRED/DERIVED per PRD rules
                initial_status = "DERIVED" if file_format.lower() in ("geojson", "shapefile") else "INFERRED"
                prop = PropertyObject(
                    three_d_property_id=three_d_id,
                    type=rec.object_type,
                    parent_id=parent_id,
                    geometry=geom_elem,
                    z_min=z_min,
                    z_max=z_max,
                    attributes={
                        **rec.attributes,
                        "geojson_geometry": rec.geojson_geometry,
                        "height": height,
                        "floor_count": floor_count,
                        "original_crs": rec.original_crs,
                    },
                    confidence=rec.source_confidence,
                    status=initial_status,
                    source_list=[str(evidence.id)],
                )
                db.add(prop)
                db.flush()

                evidence.property_object_id = prop.id

                # Record creation event
                change_event = ChangeEvent(
                    property_object_id=prop.id,
                    event_type="created",
                    old_state=None,
                    new_state={
                        "three_d_property_id": three_d_id,
                        "type": rec.object_type,
                        "parent_id": str(parent_id) if parent_id else None,
                        "status": initial_status,
                        "confidence": rec.source_confidence,
                        "height": height,
                        "z_min": z_min,
                        "z_max": z_max,
                    },
                    actor_id=operator_id,
                    evidence_id=evidence.id,
                )
                db.add(change_event)
                created_count += 1
            else:
                # Existing property: append evidence and re-fuse with past observations
                evidence.property_object_id = prop.id
                current_sources = prop.source_list or []
                if str(evidence.id) not in current_sources:
                    prop.source_list = list(current_sources) + [str(evidence.id)]
                    flag_modified(prop, "source_list")

                # Multi-observation fusion for height
                if rec.height is not None:
                    past_obs = db.query(SourceObservation).filter(
                        SourceObservation.property_object_id == prop.id,
                        SourceObservation.attribute_name == "height",
                    ).all()

                    fusion_list = []
                    for o in past_obs:
                        val = o.observed_value.get("value", 0.0) if isinstance(o.observed_value, dict) else o.observed_value
                        fusion_list.append(
                            FusionObservation(
                                value=float(val),
                                source_confidence=o.source_confidence,
                                observed_at=o.observed_at if o.observed_at else datetime.now(timezone.utc),
                                source_id=o.source_id,
                            )
                        )

                    # Append new observation
                    fusion_list.append(
                        FusionObservation(
                            value=float(rec.height),
                            source_confidence=rec.source_confidence,
                            observed_at=rec.observed_at if rec.observed_at else datetime.now(timezone.utc),
                            source_id=rec.source_id,
                        )
                    )

                    # Execute fusion with conflict detection
                    fusion_result = fuse_attribute(fusion_list, conflict_tolerance_abs=3.0, conflict_tolerance_rel=0.25)
                    old_height = prop.attributes.get("height") if prop.attributes else None
                    new_attrs = dict(prop.attributes or {})
                    new_attrs["height"] = fusion_result.fused_value
                    prop.attributes = new_attrs
                    flag_modified(prop, "attributes")
                    prop.confidence = fusion_result.fused_confidence

                    # If conflict detected beyond threshold, create a conflict record
                    if fusion_result.has_conflict:
                        conflict = Conflict(
                            property_object_id=prop.id,
                            rule_code="VR-FUS-01",
                            description=fusion_result.conflict_reason,
                            severity="WARNING",
                            status="OPEN",
                        )
                        db.add(conflict)

                    change_event = ChangeEvent(
                        property_object_id=prop.id,
                        event_type="height_updated",
                        old_state={"height": old_height},
                        new_state={
                            "height": fusion_result.fused_value,
                            "confidence": fusion_result.fused_confidence,
                            "has_conflict": fusion_result.has_conflict,
                            "observations_count": fusion_result.observations_count,
                        },
                        actor_id=operator_id,
                        evidence_id=evidence.id,
                    )
                    db.add(change_event)

            # Record raw source observations (FR-STD-04, FR-FUS-01)
            if rec.height is not None:
                obs_height = SourceObservation(
                    property_object_id=prop.id,
                    attribute_name="height",
                    observed_value={"value": rec.height, "unit": "m"},
                    source_confidence=rec.source_confidence,
                    observed_at=rec.observed_at or now,
                    source_id=rec.source_id,
                    ingestion_job_id=job.id,
                )
                db.add(obs_height)

            if rec.geometry is not None:
                obs_footprint = SourceObservation(
                    property_object_id=prop.id,
                    attribute_name="footprint",
                    observed_value=rec.geojson_geometry or {},
                    source_confidence=rec.source_confidence,
                    observed_at=rec.observed_at or now,
                    source_id=rec.source_id,
                    ingestion_job_id=job.id,
                )
                db.add(obs_footprint)

        # Post-ingestion hierarchy linking pass for batch
        all_unlinked = db.query(PropertyObject).filter(
            PropertyObject.superseded_by.is_(None),
            PropertyObject.parent_id.is_(None),
            PropertyObject.type.in_(("building", "floor", "unit")),
        ).all()
        for p in all_unlinked:
            try:
                parsed = parse_3d_property_id(p.three_d_property_id)
                if p.type == "building":
                    parcel = db.query(PropertyObject).filter(
                        PropertyObject.three_d_property_id == make_3d_property_id(parsed["ulpin"], 0, 0, 0),
                        PropertyObject.superseded_by.is_(None),
                    ).first()
                    if parcel:
                        p.parent_id = parcel.id
                elif p.type == "floor":
                    bldg = db.query(PropertyObject).filter(
                        PropertyObject.three_d_property_id == make_3d_property_id(parsed["ulpin"], parsed["building_seq"], 0, 0),
                        PropertyObject.superseded_by.is_(None),
                    ).first()
                    if bldg:
                        p.parent_id = bldg.id
                elif p.type == "unit":
                    bldg = db.query(PropertyObject).filter(
                        PropertyObject.three_d_property_id == make_3d_property_id(parsed["ulpin"], parsed["building_seq"], 0, 0),
                        PropertyObject.superseded_by.is_(None),
                    ).first()
                    if bldg:
                        p.parent_id = bldg.id
            except Exception:
                continue

        job.status = "COMPLETED"
        job.record_count = len(records)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job

    except Exception as exc:
        db.rollback()
        job.status = "FAILED"
        job.error_detail = str(exc)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job
