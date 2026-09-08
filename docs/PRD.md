# 3D Cadastral Intelligence & Property Identification System
## Production-Ready PRD for Google Antigravity

### 1. Product purpose
Build a government-oriented 3D cadastral intelligence platform that combines cadastral/geospatial data, property records, building plans, imagery/elevation evidence, and AI/GIS analysis into a versioned, evidence-backed 3D model of parcels, buildings, floors and units.

Core principles:
1. AI derives, evidence supports, authority verifies.
2. Spatial identity is separate from ownership identity.
3. Every object has provenance, confidence and status.
4. No destructive edits; changes are versioned as events.
5. Sensor-agnostic ingestion.
6. Physical, cadastral and legal layers remain separate but linked.

### 2. Primary users
- Public viewer: only aggregated/anonymized information.
- Field surveyor: submit evidence; cannot verify.
- Verifying officer: review evidence and move provisional records to verified.
- Administrator: platform configuration and administration.

### 3. MVP / Phase 1 scope
The first build must be a working pilot for one ward/locality using public/open or synthetic data:
- ~500–2,000 buildings target scale.
- Ingest GeoJSON/Shapefile, GeoTIFF DEM/DSM/orthophoto, tabular records.
- Allow future adapters for LAS/LAZ, CAD/DXF, PDFs/OCR and APIs.
- Normalize CRS and units.
- Store provenance for every ingested object.
- Fuse multiple observations using confidence and recency.
- Run deterministic topology validation.
- Generate parcel → building → floor → unit hierarchy.
- Generate immutable 3D Property IDs using ULPIN-building-floor-unit sequence.
- Provide verification queue, conflict queue, map view, search, object detail, evidence viewer, history timeline.
- Provide REST API.
- Use PostgreSQL + PostGIS; object storage for large raster/point cloud assets.
- Use rule-based height/floor estimation in MVP where source data allows.
- Keep AI outputs explicitly INFERRED/DERIVED and block AI-only verification.

### 4. Future phases
Phase 2: partner municipality, drone/oblique imagery, municipal plan PDFs, tax data and officer verification.
Phase 3: LiDAR, NAKSHA, GNSS-CORS and registration-system integrations; production-grade API integrations.
Phase 4: federated multi-state/national deployment and standardized cross-jurisdiction resolution.

### 5. Functional requirements

#### 5.1 Ingestion
FR-ING-01 Upload one or many files.
FR-ING-02 Create an asynchronous ingestion job.
FR-ING-03 Support GeoJSON, Shapefile/GPKG, GeoTIFF and CSV in MVP.
FR-ING-04 Record original format, CRS, source, operator/job ID and timestamp.
FR-ING-05 Normalize to a configured working CRS and normalized units.
FR-ING-06 Preserve raw input references; do not silently discard source data.
FR-ING-07 Provide job progress and failure reason.

#### 5.2 Standardization
FR-STD-01 Map source fields into canonical schema.
FR-STD-02 Normalize geometry and units.
FR-STD-03 Validate geometry before downstream processing.
FR-STD-04 Store source observations rather than overwriting previous observations.

#### 5.3 Data fusion
FR-FUS-01 Store all observations for attributes such as footprint, height and floor count.
FR-FUS-02 Compute fused values using source reliability × recency decay.
FR-FUS-03 Flag conflicts when values differ beyond a configurable tolerance.
FR-FUS-04 Never hide conflicts by silently averaging contradictory evidence.
FR-FUS-05 Allow re-fusion later from preserved observations.

#### 5.4 AI/GIS analysis
FR-AI-01 Provide an analysis interface with pluggable algorithms.
FR-AI-02 MVP footprint extraction may use pretrained/open building-footprint models where imagery is available.
FR-AI-03 Height may be derived from DSM−DEM where possible.
FR-AI-04 MVP floor count may estimate from height / calibrated floor-height heuristic.
FR-AI-05 All AI estimates must carry confidence and evidence references.
FR-AI-06 Deterministic topology rules remain authoritative for geometry validation.

#### 5.5 3D semantic model
FR-3D-01 Support parcel, building, floor and unit object types.
FR-3D-02 Keep parent-child relationships explicit.
FR-3D-03 Store geometry in PostGIS and semantic attributes in JSONB.
FR-3D-04 Support z_min/z_max for vertical extent.
FR-3D-05 Generate a 3D Property ID once.
FR-3D-06 Never reuse an old ID.
FR-3D-07 Split/merge events create new IDs and supersede old IDs.

ID pattern:
{ULPIN}-{building_seq}-{floor_seq}-{unit_seq}
Example: INMH0234567-B001-F04-U402

#### 5.6 Validation
VR-01 Building footprint must be inside parcel within tolerance.
VR-02 Detect unit overlap on same floor.
VR-03 Detect unexpected gaps where appropriate.
VR-04 Detect vertical overlap between floors.
VR-05 Detect building boundary violation.
VR-06 Detect near-duplicate geometry.
VR-07 Detect orphan building/floor/unit records.
VR-08 Failed validation creates a conflict record.
VR-09 Conflicts block VERIFIED status but do not block ingestion.

#### 5.7 Evidence and status
Statuses:
SYNTHETIC → INFERRED → DERIVED → PROVISIONAL → VERIFIED

- SYNTHETIC = demo/placeholder.
- INFERRED = AI-estimated, not directly measured.
- DERIVED = computed from measured sources.
- PROVISIONAL = fused/validated but awaiting human sign-off.
- VERIFIED = authorized officer confirms against authoritative evidence.

Every object stores confidence 0–1 and evidence/provenance references.

#### 5.8 Legal linkage
Ownership must be separate from spatial identity.
`property_records` references a `three_d_property_id`.
Linkage states: UNLINKED, LINKED, DISPUTED.
AI must never infer legal ownership.
Registration data is synchronized from authoritative systems/exports.

#### 5.9 Temporal versioning
Use `change_events` as immutable history:
created, height_updated, floor_added, unit_split, unit_merged, verified, superseded, demolished.
Store old_state, new_state, actor, timestamp and evidence reference.
Current-state tables are materialized/derived from events.

#### 5.10 Government UI
Provide:
- 2D/3D map.
- Search by ULPIN / 3D Property ID.
- Optional permissioned owner search.
- Verification queue.
- Conflict dashboard.
- Evidence panel.
- Object history timeline/date slider.
- Ingestion job monitor.
- Data-quality indicators.

#### 5.11 Security
RBAC roles must be enforced server-side.
Owner identity data has stricter permissioning and audit logging.
Only authenticated verifying officers can move PROVISIONAL → VERIFIED.
Public exports redact or aggregate PII.

### 6. Non-functional requirements
- APIs documented with OpenAPI.
- Async processing for heavy GIS jobs.
- Idempotent ingestion jobs.
- Structured logs with correlation/job IDs.
- Health/readiness endpoints.
- Database migrations.
- Automated tests.
- Docker-based local development.
- Configuration through environment variables.
- No secrets committed to git.
- Scalable service boundaries so algorithms can be replaced without changing identity/schema contracts.

### 7. Canonical data model
Core entities:
- parcels
- cadastral_objects / property_objects
- source_observations
- evidence
- conflicts
- property_records
- change_events
- ingestion_jobs
- users / roles

Suggested property object:
id, type, parent_id, geometry, z_min, z_max, attributes(JSONB), confidence, status, source_list, created_at, superseded_by.

### 8. API contract (initial)
GET /health
POST /api/v1/ingestion/jobs
GET /api/v1/ingestion/jobs/{job_id}
GET /api/v1/properties
GET /api/v1/properties/{three_d_property_id}
GET /api/v1/properties/{three_d_property_id}/history
GET /api/v1/conflicts
POST /api/v1/properties/{three_d_property_id}/verify
POST /api/v1/properties/{three_d_property_id}/reject
GET /api/v1/search?q=
GET /api/v1/map/objects?bbox=

### 9. Acceptance criteria
A build is accepted when:
1. A test GeoJSON/CSV/GeoTIFF dataset can be ingested end-to-end.
2. Provenance is stored for each source observation.
3. At least one fusion calculation produces a confidence score.
4. Topology violations become conflict records.
5. A parcel/building/floor/unit hierarchy can be viewed.
6. 3D IDs are immutable across updates.
7. An officer can verify a provisional record with an auditable event.
8. An unauthorised user cannot verify.
9. History remains queryable.
10. The UI can show map objects, conflicts and evidence metadata.
11. No AI-derived record is automatically marked VERIFIED.
12. Tests and setup instructions pass in a clean local environment.

### 10. Out of scope for MVP
- Legal ownership inference.
- Nationwide authoritative integrations.
- Fully autonomous interpretation of scanned building plans.
- Autonomous execution of legal/administrative decisions.
- Full national-scale Kubernetes deployment.
- Guaranteed survey-grade accuracy from low-quality open data.

### 11. Technology baseline
Backend: Python + FastAPI + SQLAlchemy/Alembic.
GIS: GDAL/GeoPandas/Shapely/Rasterio.
Async jobs: Celery + Redis (or equivalent queue).
Database: PostgreSQL + PostGIS.
Object storage: S3-compatible/MinIO.
AI/ML: PyTorch or scikit-learn depending on task.
Frontend: React + CesiumJS, MapLibre for 2D/lightweight views.
Auth: OAuth2/OIDC; production target Keycloak or government identity integration.
Deployment: Docker first; Kubernetes later.
Monitoring: Prometheus/Grafana + structured logs.

### 12. Antigravity implementation rules
- Work phase-by-phase; do not attempt all four phases at once.
- Before writing code, create a repository plan and preserve the contracts above.
- Prefer working MVP functionality over placeholder UI.
- Never fabricate authoritative legal/ownership data.
- Seed synthetic/demo data where authoritative data is unavailable.
- Add tests for every service and critical rule.
- Keep configuration and schema versioned.
- Do not rewrite existing correct modules when adding a new adapter.
- Any change to identity rules must be explicit and backward-compatible.
