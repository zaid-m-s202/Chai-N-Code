# Antigravity Master Prompt + Phase Prompts

## MASTER PROMPT
You are the lead engineer for the 3D Cadastral Intelligence & Property Identification System.
Use `docs/PRD.md` as the product source of truth.

Build the repository as a production-structured MVP, not a mockup. Preserve these non-negotiable rules:
- AI derives; evidence supports; authority verifies.
- 3D Property ID identifies space, not owner.
- Every object has provenance, confidence and status.
- No destructive edits; history is event-sourced.
- Physical, cadastral and legal layers are separate.
- Sensor-agnostic ingestion adapters.
- Do not invent legal or authoritative property facts.

Start by inspecting the repository. Create/modify only what is necessary. After each phase:
1. run backend tests,
2. run frontend tests/build,
3. run lint/type checks,
4. update README,
5. report exact files changed and remaining risks.

Do not replace working architecture with a simpler demo just to make it look finished.

## PHASE 0 — Repository and local environment
Goal: create a runnable monorepo.
Deliver:
- backend FastAPI service
- frontend React app
- PostGIS-compatible database setup
- Redis
- Docker Compose
- environment example
- migrations
- health endpoints
- README with exact commands
Acceptance: one command brings up services; frontend reaches backend health endpoint.

## PHASE 1 — Core data model and ingestion
Implement:
- property object model
- source observations
- evidence
- conflicts
- ingestion jobs
- provenance metadata
- GeoJSON and CSV import first
- asynchronous job execution
- idempotency
- API endpoints
Acceptance:
- upload sample dataset
- job status changes
- records appear in PostGIS
- source metadata is queryable.

## PHASE 2 — GIS normalization and fusion
Implement:
- CRS normalization
- unit normalization
- geometry validation
- source-weighted confidence
- recency decay
- conflict thresholds
- fusion service
- test fixtures for conflicting observations
Acceptance:
- multiple observations create fused values
- conflicting observations generate conflicts
- raw observations remain preserved.

## PHASE 3 — 3D semantic model
Implement:
- parcel/building/floor/unit hierarchy
- z_min/z_max
- configurable floor-height heuristic
- immutable 3D Property IDs
- split/merge/supersession events
Acceptance:
- sample parcels render with hierarchy
- IDs remain stable across updates
- split/merge never reuses old IDs.

## PHASE 4 — Validation and verification
Implement deterministic topology rules:
- containment
- overlap
- gap/anomaly
- vertical consistency
- boundary violation
- duplicate detection
- orphan detection
Build officer review queue and verify/reject endpoints.
Acceptance:
- failed rules create conflicts
- conflicts prevent VERIFIED status
- verification creates an audit event
- only authorized verifying officers can verify.

## PHASE 5 — Frontend 2D/3D government UI
Implement:
- map
- property search
- object detail drawer
- evidence panel
- conflict dashboard
- verification queue
- timeline/history
- ingestion jobs screen
- role-aware controls.
Use CesiumJS for 3D when the data is ready; use MapLibre for 2D/lightweight layers.
Acceptance: an officer can find a property, inspect evidence, see conflicts/history and verify it.

## PHASE 6 — AI/GIS analysis adapters
Implement interfaces first, then MVP algorithms:
- height from DSM−DEM where inputs exist
- floor estimation from height heuristic
- optional pretrained footprint extraction interface
- confidence/evidence attachment
Do not let AI outputs bypass status gating.

## PHASE 7 — Legal linkage
Implement schema/API for property_records:
- three_d_property_id
- ULPIN
- owner_party_id
- registration_number/date
- rights_type
- encumbrances
- linkage_status
- source system/sync time
Keep owner data behind stricter RBAC and audit logging.
Do not infer owner identity.

## PHASE 8 — Production hardening
Add:
- OpenAPI docs cleanup
- rate limits where appropriate
- audit log review
- structured logging
- metrics
- backup/restore instructions
- security headers
- CI
- data export with PII redaction
- schema/version compatibility tests.

## PHASE 9 — Deliverable documentation
Create:
- architecture document (max 2 pages)
- setup README
- API guide
- data model document
- operator guide
- demo seed data
- test report template
- pilot checklist.

## RULE FOR FUTURE ENHANCEMENTS
New sensors, vendors, jurisdictions, algorithms and authoritative data integrations must plug into adapters/services without changing the 3D Property ID semantics or legal separation model.
