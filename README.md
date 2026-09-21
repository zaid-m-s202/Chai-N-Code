# 3D Cadastral Intelligence & Property Identification System

Production-structured MVP pilot for an evidence-backed government 3D cadastral intelligence platform .

Combines cadastral/geospatial parcel footprints, tabular survey observations, building height/floor records, and deterministic topology validation into an event-sourced, versioned 3D spatial hierarchy (**parcel → building → floor → unit**).

---

## Non-Negotiable Core Principles

1. **AI derives; evidence supports; authority verifies.** AI outputs start as `INFERRED`/`DERIVED`. Only authenticated verifying officers can promote records to `VERIFIED`.
2. **3D Property ID identifies space, not owner.** Format: `{ULPIN}-{building_seq:03d}-F{floor_seq:02d}-U{unit_seq:03d}` (e.g. `INMH0234567-B001-F04-U402`). Space identity is strictly decoupled from legal ownership.
3. **Every object has provenance, confidence, and status.** Status progression: `SYNTHETIC` → `INFERRED` → `DERIVED` → `PROVISIONAL` → `VERIFIED`.
4. **No destructive edits; history is event-sourced.** All operations log immutable `change_events`. Current state is derived; records are soft-retired via `superseded_by`.
5. **Sensor-agnostic ingestion adapters.** GeoJSON, CSV/WKT supported in MVP with standardized `CanonicalRecord` intermediate representation.
6. **Physical, cadastral, and legal layers are separate.**
7. **Do not invent legal or authoritative property facts.**

---

## Directory Structure

```text
├── docs/
│   ├── ARCHITECTURE.md            # Architecture & technical design (max 2 pages)
│   ├── SETUP.md                   # Comprehensive setup & installation guide
│   ├── API_GUIDE.md               # REST API technical reference & schemas
│   ├── DATA_MODEL.md              # Data model, ER diagrams & lifecycle state machine
│   ├── OPERATOR_GUIDE.md          # Government operator guide & SOP manual
│   ├── TEST_REPORT_TEMPLATE.md    # Pilot acceptance test report template
│   ├── PILOT_CHECKLIST.md         # Municipal pilot rollout checklist
│   ├── BACKUP_RESTORE.md          # Disaster recovery & automated backup runbook
│   ├── PRD.md                     # Product source of truth
│   └── ANTIGRAVITY_PROMPTS.md     # Phase prompts & implementation roadmap
├── sample_data/
│   ├── demo_cadastral_dataset.json      # Rich multi-tier Indian urban pilot dataset
│   ├── ward_pilot_footprints.geojson    # Sample parcel & building footprints
│   ├── ward_pilot_survey.csv            # Sample tabular floor/unit survey records
│   ├── conflicting_observations.csv     # Phase 2 test fixture: multi-source elevation discrepancies & unit mix
│   └── conflicting_observations.geojson # Phase 2 test fixture: contradictory GeoJSON building heights
├── src/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/               # FastAPI endpoints (auth, properties, ingestion, conflicts, search, map, legal, audit, export)
│   │   │   ├── models/            # SQLAlchemy models (PropertyObject, Evidence, SourceObservation, Conflict, ChangeEvent, PropertyRecord)
│   │   │   ├── schemas/           # Pydantic validation schemas
│   │   │   ├── services/          # ID generator, fusion, geometric validation, topology runner
│   │   │   ├── ingestion/         # Sensor-agnostic adapters (GeoJSON, CSV) & pipeline
│   │   │   ├── seeds/             # Standalone demo cadastral database seeder
│   │   │   ├── config.py          # Environment settings
│   │   │   ├── database.py        # Engine, session, PostGIS support
│   │   │   ├── metrics.py         # Prometheus telemetry exporter
│   │   │   ├── middleware.py      # Security headers, rate limiting & structured logging
│   │   │   └── main.py            # FastAPI entrypoint & CORS
│   │   ├── alembic/               # Database migrations
│   │   ├── tests/                 # Automated test suite (117+ tests)
│   │   ├── Dockerfile             # Container image
│   │   └── requirements.txt       # Python dependencies
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── api/client.ts      # Typed REST API client
│   │   │   ├── components/        # StatusBadge, UI components
│   │   │   ├── pages/             # Properties, Map, Ingestion, Conflicts
│   │   │   ├── App.tsx            # Navigation & application shell
│   │   │   └── styles.css         # Modern government portal design system
│   │   ├── package.json           # React 18 + Vite + TypeScript
│   │   └── tsconfig.json          # TypeScript configuration
│   └── infra/
│       └── docker-compose.yml     # PostGIS 16 + Redis + Backend stack
└── README.md
```

---

## Quickstart: One-Command Launch (Phase 0 Acceptance)

Bring up all services (**PostGIS 16**, **Redis 7**, **FastAPI Backend**, and **React Frontend**) in a single command from the project root:

```bash
docker compose up --build
```

Once up:
- **Government Portal (Frontend)**: `http://localhost:5173` (or `http://localhost:3000`)
- **Interactive OpenAPI Documentation**: `http://localhost:8000/docs`
- **Liveness Health Check**: `http://localhost:8000/health`
- **Readiness Probe**: `http://localhost:8000/health/ready`

The frontend immediately queries the backend health endpoint upon mount and displays a live connection status pill in the header.

---

## Local Development Setup

### 1. Backend Service

```bash
cd src/backend

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations (ensure PostGIS is running or configured in .env)
alembic upgrade head

# Start API server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Application

```bash
cd src/frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

Visit `http://localhost:5173` to access the government portal.

---

## Running Verification & Tests

### Backend Automated Tests

Run the full suite of unit and integration tests (uses isolated in-memory SQLite):

```bash
cd src/backend
python -m pytest tests/ -v
```

Tests cover:
- **3D Property ID Generation**: Format adherence, immutability, sequence padding (`test_id_generator.py`)
- **GIS Normalization**: CRS reprojection from EPSG:3857 to EPSG:4326, unit conversion (feet/inches to meters), geometry validation and topological repair (`test_normalization.py`)
- **Observation Fusion**: Recency decay, source confidence weighting, conflict thresholds, consensus agreement boost, and confidence penalties on dispute (`test_fusion.py`)
- **Deterministic Topology Validation (VR-01 through VR-09)**: Containment (`VR-01`), unit overlap (`VR-02`), gap anomalies (`VR-03`), vertical consistency (`VR-04`), boundary violations (`VR-05`), near-duplicate detection (`VR-06`), orphan detection (`VR-07`), conflict generation (`VR-08`), and verification blocking (`VR-09`) (`test_topology_validation.py`)
- **Ingestion Pipeline**: GeoJSON and CSV parsing, provenance tracking, multi-source ingestion, conflicting observations generating open conflicts, raw observation preservation (`test_ingestion.py`)
- **API & RBAC Security**: Public endpoints, search, map layers, observations query, re-fusion endpoint, verifying officer authorization gating, conflict blocking, verification queue, and rejection audit logging (`test_api.py`, `test_topology_validation.py`)

### Frontend Typecheck & Production Build

```bash
cd src/frontend
npm run build
```

---

## Core REST API Endpoints

| Method | Endpoint | Description | Auth / Role |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Liveness health probe | Public |
| `GET` | `/health/ready` | Readiness health probe (DB connectivity) | Public |
| `POST` | `/api/v1/auth/login` | Authenticate user & issue JWT | Public |
| `POST` | `/api/v1/auth/quick-token` | Issue signed JWT for requested role (demo/testing) | Public |
| `GET` | `/api/v1/auth/me` | Current authenticated user profile | Authenticated |
| `POST` | `/api/v1/ingestion/jobs` | Upload GeoJSON/CSV for asynchronous ingestion | Surveyor / Officer / Public |
| `GET` | `/api/v1/ingestion/jobs/{id}`| Poll ingestion job status, record count & errors | Public |
| `GET` | `/api/v1/properties` | List active properties with status/type filters | Public |
| `GET` | `/api/v1/properties/{id}` | Full spatial & semantic attributes of property | Public |
| `GET` | `/api/v1/properties/{id}/history` | Event-sourced immutable change timeline | Public |
| `GET` | `/api/v1/properties/{id}/evidence`| Provenance & source metadata for property | Public |
| `GET` | `/api/v1/properties/{id}/observations`| Preserved raw source observations (append-only) | Public |
| `POST` | `/api/v1/properties/{id}/refuse` | Re-execute multi-source observation fusion | Public / Officer |
| `POST` | `/api/v1/properties/{id}/verify` | Promote record to `VERIFIED` (blocked by conflicts) | **Verifying Officer / Admin** |
| `POST` | `/api/v1/properties/{id}/reject` | Reject provisional record with officer notes | **Verifying Officer / Admin** |
| `GET` | `/api/v1/verification-queue` | Officer review queue of PROVISIONAL records | Public / Officer |
| `GET` | `/api/v1/conflicts/verification-queue` | Officer review queue with conflict filter | Public / Officer |
| `GET` | `/api/v1/conflicts` | List active boundary, topology & fusion conflicts | Public / Officer |
| `POST` | `/api/v1/conflicts/run-topology` | Batch run deterministic topology rules (VR-01–07)| **Verifying Officer / Admin** |
| `POST` | `/api/v1/conflicts/{id}/resolve` | Mark conflict resolved | **Verifying Officer / Admin** |
| `POST` | `/api/v1/conflicts/{id}/waive` | Waive conflict as non-blocking | **Verifying Officer / Admin** |
| `GET` | `/api/v1/search?q=` | Search by 3D Property ID or ULPIN | Public |
| `GET` | `/api/v1/map/objects?bbox=` | GeoJSON FeatureCollection map layer | Public |
| `GET` | `/api/v1/analysis/adapters` | List registered AI/GIS analysis adapters | Public |
| `POST` | `/api/v1/analysis/dsm-dem-height` | Derive building height from DSM minus DEM (`nDSM`) | Public / Operator |
| `POST` | `/api/v1/analysis/estimate-floors` | Infer floor levels & vertical intervals `[z_min, z_max]` | Public / Operator |
| `POST` | `/api/v1/analysis/extract-footprints` | Extract & vectorize building footprints with simplification | Public / Operator |
| `POST` | `/api/v1/properties/{id}/analyze` | Execute full AI spatial analysis on a property record | Public / Operator |
| `POST` | `/api/v1/legal/records` | Link external cadastral/legal registry record (ULPIN, deed, rights) | **Verifying Officer / Admin** |
| `GET` | `/api/v1/legal/records` | Search/list legal records (Role-aware: unredacted for officers, redacted for public/surveyors) | Public / Officer |
| `GET` | `/api/v1/legal/records/{id}` | Get legal record by ID (Role-aware) | Public / Officer |
| `GET` | `/api/v1/legal/by-property/{id}`| Get all legal records linked to a 3D PropertyObject | Public / Officer |
| `PUT` | `/api/v1/legal/records/{id}` | Update rights type, encumbrances, or sync metadata | **Verifying Officer / Admin** |
| `DELETE`| `/api/v1/legal/records/{id}` | Soft-unlink legal record (`UNLINKED` status) | **Verifying Officer / Admin** |
| `GET` | `/metrics` | Prometheus telemetry & JSON observability metrics | Public / Monitoring |
| `GET` | `/api/v1/audit/events` | Query and filter immutable compliance change events | **Verifying Officer / Admin** |
| `GET` | `/api/v1/audit/summary` | Aggregated compliance metrics and event distribution | **Verifying Officer / Admin** |
| `GET` | `/api/v1/export/cadastral` | Bulk tabular export (JSON/CSV) with automated PII redaction | Public / Officer |
| `GET` | `/api/v1/export/geojson` | Bulk 3D spatial GeoJSON FeatureCollection export | Public / Officer |

---

## Testing the End-to-End Workflow (Phase 5–8 Acceptance)

1. **Role-Aware Authority Control & Cadastral Privacy**:
   - In the top-right header, select **Active Role**:
     - `🛡️ Verifying Officer (Authority)`: Full authority to verify/reject properties, run topology validation, resolve/waive conflicts, manage/view confidential owner identity records, review audit logs, and export unmasked datasets.
     - `📐 Field Surveyor (Submitter)`: Submits ingestion data and views records; verification, audit log review, and unmasked owner identity are protected.
     - `👁️ Public Viewer (Read-Only)`: Read-only cadastral view with confidential owner data automatically redacted.
2. **Data Ingestion**:
   - Navigate to **Ingestion & Provenance** (`http://localhost:5173`).
   - Click one of the quick-load sample buttons (e.g. `ward_pilot_footprints.geojson` or `ward_pilot_survey.csv`), or upload your own file.
   - Observe the live job monitor logging record counts and provenance hashes.
3. **Interactive 2D/3D Spatial Map**:
   - Switch to **2D/3D Spatial Map**:
     - **2D Map (MapLibre)**: Flat cadastral parcel boundaries.
     - **3D Extrusions (WebGL)**: Building footprints extruded by height heuristic in 3D perspective with realistic shadows and pitch controls.
     - **3D Globe (CesiumJS)**: 3D globe telemetry and terrain mode.
     - Click any building or parcel on the map to inspect its spatial attributes, vertical Z bounds, and semantic metadata.
4. **Officer Review Queue**:
   - Switch to **Officer Verification Queue**:
     - Filter between "All Provisional", "Ready for Sign-off (Clean)", and "Blocked by Conflicts".
     - Select a provisional record to open its review dossier.
5. **Inspect Evidence & Conflicts**:
   - Review the **3D Spatial Hierarchy** (`parcel → building → floor → unit`).
   - Inspect **Provenance Evidence** (source system, original CRS, SHA256 file hash).
   - Inspect **Preserved Source Observations** and run on-demand consensus re-fusion.
   - Inspect the **Event History Timeline** (event-sourced immutable trail).
6. **Authoritative Verification & Conflict Enforcement**:
   - If a record has open conflicts, rule VR-09 blocks verification with a conflict alert.
   - Switch to **Topology Conflicts**, inspect rule violations (VR-01 through VR-08), and click **Resolve** or **Waive**.
   - Return to the property dossier, enter official verification notes, and click **Sign & Authorize (Verify)**.
   - Status updates to `VERIFIED`, confidence becomes `1.0`, and an immutable `verified` audit event is logged.
7. **AI / GIS Spatial Analysis & Status Gating (Phase 6 Acceptance)**:
   - Open any property record in the **Property Dossier** drawer.
   - In the **🤖 AI / GIS Spatial Analysis** panel, adjust DSM surface elevation (m), DEM terrain elevation (m), and occupancy/use type (e.g. Residential 3.0m, Commercial 3.8m).
   - Click **⚡ Execute AI Spatial Pipeline (Height + Floors)**.
   - Observe:
     - Building height derived via `nDSM = DSM - DEM`.
     - Per-level 3D vertical intervals `[z_min, z_max]` sliced automatically.
     - **Strict Status Gating**: The property record is promoted to `DERIVED` or `INFERRED`, but **never** `VERIFIED`. An authorized officer must independently verify the record.
     - New `SourceObservation` entries (`height`, `floor_count`) and an `ai_analysis_run` provenance `Evidence` record are permanently attached with audit `change_events`.
8. **Legal & Land Registry Linkage (Phase 7 Acceptance)**:
   - In the **🏛️ Legal & Land Registry Linkage** panel in the property dossier drawer:
     - **Decoupled Identity**: Spatial coordinates identify *space*; legal titles identify *rights*. Owner identities are **never inferred** or synthesized by AI.
     - **Strict RBAC & Privacy Protection**: When logged in as **Verifying Officer / Admin**, the full `owner_party_id` is visible and verifiable. When switched to **Public Viewer** or **Field Surveyor**, owner identities are automatically redacted to `🔒 Protected by Cadastral Privacy RBAC`.
     - **Authoritative Linkage**: Officers can link external ULPINs, deed registration numbers, dates, tenure rights (`freehold`, `leasehold`, `strata_title`, `easement`), and encumbrance/mortgage charges.
     - **Audit Logging**: Every linkage creation, update, and unlinking operation produces an immutable `change_event` in the audit timeline.
9. **Production Hardening & Compliance Observability (Phase 8 Acceptance)**:
   - **Prometheus Telemetry**: Query `http://localhost:8000/metrics` or `http://localhost:8000/metrics?format=json` to monitor process uptime, latency, request rates, active 3D property status distributions, and open topology conflicts.
   - **Enterprise Security**: Inspect response headers for OWASP compliance (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Referrer-Policy`, and correlated `X-Request-ID`).
   - **PII-Redacted Bulk Data Export**: Download cadastral datasets in JSON or CSV via `/api/v1/export/cadastral`. By default, owner identities are masked (`[REDACTED]`). Unmasked downloads require officer authorization and explicit justification, generating audit logs.
   - **Audit Log Compliance**: Review event-sourced change histories and aggregations via `/api/v1/audit/events` and `/api/v1/audit/summary`.
   - **Automated CI & Disaster Recovery**: GitHub Actions pipeline defined in `.github/workflows/ci.yml` and enterprise disaster recovery runbook in [`docs/BACKUP_RESTORE.md`](docs/BACKUP_RESTORE.md).
10. **Deliverable Documentation & Demo Seeding (Phase 9 Acceptance)**:
    - **Architecture Document (Max 2 Pages)**: Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for executive principles, C4 component decomposition, and geodetic specifications.
    - **Setup & Installation Guide**: Follow [`docs/SETUP.md`](docs/SETUP.md) for native and containerized deployment instructions.
    - **API Technical Reference**: Consult [`docs/API_GUIDE.md`](docs/API_GUIDE.md) for request/response schemas, role permissions, and cURL snippets.
    - **Data Model & ER Specifications**: Review [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) for database tables, indexes, and lifecycle state machines.
    - **Government Operator Guide & SOPs**: Step-by-step operational workflows in [`docs/OPERATOR_GUIDE.md`](docs/OPERATOR_GUIDE.md).
    - **Demo Cadastral Seed Dataset**: Inspect [`sample_data/demo_cadastral_dataset.json`](sample_data/demo_cadastral_dataset.json) or run `python -m app.seeds.seed_demo_data` to seed realistic Indian urban wards (Pune/Bengaluru), deliberate topology conflicts, and legal land records.
    - **Pilot Acceptance Test Report**: Use [`docs/TEST_REPORT_TEMPLATE.md`](docs/TEST_REPORT_TEMPLATE.md) for statutory sign-off and QA certification.
    - **Municipal Pilot Rollout Checklist**: Plan deployment milestones using [`docs/PILOT_CHECKLIST.md`](docs/PILOT_CHECKLIST.md).
