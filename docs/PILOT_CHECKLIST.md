# 3D Cadastral Intelligence System — Municipal Pilot Rollout Checklist

This checklist defines the milestone requirements, operational gates, and statutory verification steps for deploying the **3D Cadastral Intelligence & Property Identification Platform** in a municipal ward or state land records pilot.

---

## Milestone 1: Pre-Pilot Governance & Infrastructure (T-30 to T-14 Days)

- [ ] **Infrastructure Provisioning**:
  - [ ] Virtual Machine / Kubernetes cluster deployed (Minimum: 4 vCPU, 16 GB RAM, NVMe SSD).
  - [ ] PostgreSQL 16 provisioned with **PostGIS 3.4+** extension enabled.
  - [ ] Redis 7.0+ provisioned for rate limiting and asynchronous worker queues.
  - [ ] S3-compatible Object Storage (MinIO or AWS S3) configured for raw survey evidence blob archival.
- [ ] **Security & Network Perimeter**:
  - [ ] TLS 1.3 certificate installed and configured with automatic renewal.
  - [ ] OWASP security headers verified (`HSTS`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`).
  - [ ] Internal API firewall and ingress controller configured; rate limiting tested.
  - [ ] Cryptographically random 256-bit `SECRET_KEY` generated and injected via secrets manager.
- [ ] **Disaster Recovery & Backup Readiness**:
  - [ ] Automated daily `pg_dump` and continuous WAL archiving configured per [`docs/BACKUP_RESTORE.md`](BACKUP_RESTORE.md).
  - [ ] Restore drill successfully executed into an isolated staging instance.

---

## Milestone 2: Geodetic Datum & Sensor Calibration (T-14 to T-7 Days)

- [ ] **Geodetic & Projection Standards**:
  - [ ] Target projection locked to **WGS 84 (`EPSG:4326`)**; coordinate order confirmed as `[longitude, latitude]`.
  - [ ] Elevation datum defined (ellipsoidal vs MSL orthometric); vertical unit locked to meters ($m$).
  - [ ] Local state survey projection parameters (e.g. UTM Zone 43N / EPSG:32643) mapped in the normalizer.
- [ ] **Sensor Quality Tolerances**:
  - [ ] Drone LiDAR / Photogrammetry: Ground Sample Distance (GSD) $\le 3\text{ cm/pixel}$; minimum 5 Ground Control Points (GCPs) per square kilometer.
  - [ ] DGPS Total Station: Horizontal accuracy $\le 0.05\text{ m}$; vertical accuracy $\le 0.10\text{ m}$.
  - [ ] Architectural As-Built CAD: Minimum 3 geo-referenced tie points matching municipal cadastral grid.

---

## Milestone 3: Stakeholder Credentialing & RBAC Setup (T-7 to T-2 Days)

- [ ] **Account Creation & Role Provisioning**:
  - [ ] Statutory Verifying Officers issued hardware tokens or secure credentials with `VERIFYING_OFFICER` role.
  - [ ] Field survey teams issued field accounts with `FIELD_SURVEYOR` role.
  - [ ] System engineers granted `ADMIN` role.
  - [ ] Public anonymous viewer endpoints verified for automated PII masking.
- [ ] **Standard Operating Procedure (SOP) Training**:
  - [ ] All verifying officers trained on **Rule VR-09** (conflicts blocking verification) and conflict resolution protocols.
  - [ ] Field teams briefed on GeoJSON/CSV formatting and cryptographic hash receipts.
  - [ ] Data protection training completed on confidential `owner_party_id` handling and export justification.

---

## Milestone 4: Staging Dry Run & Trial Ingestion (T-2 to T-1 Days)

- [ ] **Trial Data Ingestion**:
  - [ ] Ingestion of baseline ward parcel boundaries (`ward_pilot_footprints.geojson`) completed successfully.
  - [ ] Tabular interior floor/unit survey records (`ward_pilot_survey.csv`) ingested.
  - [ ] Cryptographic SHA-256 evidence records verified in the database.
- [ ] **Deterministic Topology Engine Verification**:
  - [ ] Batch topology validation executed via `/api/v1/conflicts/run-topology`.
  - [ ] Confirmed that intentional test overlaps (VR-02) and height gaps (VR-04) appear in the officer conflict register.
  - [ ] Verified that attempting to verify an overlapping unit returns `HTTP 409 Conflict` under Rule VR-09.
  - [ ] Conflict resolution and waiver workflow verified by an authenticated officer.
- [ ] **AI/GIS Analysis Adapter Smoke Test**:
  - [ ] Tested $n\text{DSM}$ calculation: Building height successfully derived from $\text{DSM} - \text{DEM}$.
  - [ ] Verified that AI-derived records are strictly labeled `DERIVED` and cannot bypass the officer verification queue.

---

## Milestone 5: Day-0 Go-Live Operations

- [ ] **Go-Live Activation**:
  - [ ] Production database migrations confirmed at `head` (`alembic upgrade head`).
  - [ ] Production demo seed script executed or initial ward baseline loaded.
  - [ ] Frontend portal deployed and pointing to production backend URL.
  - [ ] Real-time health probes confirmed (`/health` and `/health/ready` returning `200 OK`).
  - [ ] Prometheus telemetry scraping verified (`/metrics`).
- [ ] **Officer Queue Live Triage**:
  - [ ] Verifying officers logged in and viewing the active verification queue.
  - [ ] First batch of clean provisional records formally verified and signed off.
  - [ ] Change event audit trail confirmed recording immutable event-sourced records.

---

## Milestone 6: Post-Launch Operational Governance (Day 1 to Day 30)

- [ ] **Daily & Weekly Review Cadence**:
  - [ ] **Daily**: Monitor Prometheus `/metrics` for rate-limit violations, ingestion error counts, and queue depth.
  - [ ] **Weekly**: Convene the Municipal Cadastral Conflict Review Committee to resolve contested boundary disputes.
  - [ ] **Bi-Weekly**: Audit unmasked PII export logs via `/api/v1/audit/events` to ensure compliance with privacy regulations.
  - [ ] **Monthly**: Execute disaster recovery backup restoration drill.
