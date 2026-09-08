# 3D Cadastral Intelligence System — Comprehensive Setup & Installation Guide

This guide details instructions for setting up, configuring, seeding, and verifying the **3D Cadastral Intelligence & Property Identification Platform** in development, testing, and production environments.

---

## 1. System Requirements & Prerequisites

### Minimum Hardware
- **CPU**: 4 Cores (x86_64 or ARM64)
- **RAM**: 8 GB minimum (16 GB recommended for 3D geospatial rendering and drone point-cloud processing)
- **Disk**: 20 GB free storage (SSD recommended)

### Software Prerequisites
- **Docker Engine**: Version 24.0+ and **Docker Compose** v2.20+
*OR for native bare-metal execution:*
- **Python**: 3.11, 3.12, 3.13, or 3.14
- **Node.js**: v18.x, v20.x, or v22.x LTS with `npm` v9+
- **PostgreSQL**: v15 or v16 with **PostGIS** extension v3.3+ (Optional: SQLite in-memory mode supported for fast testing)
- **Redis**: v6.2 or v7.0+ (Optional for local development)

---

## 2. Quickstart: One-Command Docker Launch

The fastest way to deploy the entire production-structured stack (**PostGIS 16**, **Redis 7**, **FastAPI Backend**, and **Vite React Frontend**) is via Docker Compose:

```bash
# 1. Clone the repository and enter the directory
git clone https://github.com/your-org/3d-cadastral-system.git
cd 3d-cadastral-system

# 2. Copy the sample environment file
cp .env.example .env

# 3. Build and launch all containers
docker compose up --build -d
```

### Verification & Health URLs
Once initialized, the services will be reachable at:
- **Government Web Portal (Frontend)**: [http://localhost:5173](http://localhost:5173) (or `http://localhost:3000`)
- **FastAPI Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Liveness Probe**: [http://localhost:8000/health](http://localhost:8000/health)
- **Database Readiness Probe**: [http://localhost:8000/health/ready](http://localhost:8000/health/ready)
- **Prometheus Observability Metrics**: [http://localhost:8000/metrics](http://localhost:8000/metrics)

To shut down the containers:
```bash
docker compose down
```

---

## 3. Native Local Development Setup

Follow these steps to run the backend and frontend services natively without Docker containers.

### A. Backend Service Setup (Python / FastAPI)

1. **Navigate to the backend directory:**
   ```bash
   cd src/backend
   ```

2. **Create and activate a virtual environment:**
   - **Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
   - **Linux / macOS:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   Create a `.env` file in `src/backend/.env` (or copy from `.env.example`):
   ```ini
   # For local development with SQLite (no Postgres needed):
   DATABASE_URL=sqlite:///./cadastral_dev.db
   REDIS_URL=redis://localhost:6379/0
   SECRET_KEY=dev-secret-key-3d-cadastre-local-only-min-32-chars
   ACCESS_TOKEN_EXPIRE_MINUTES=480
   LOG_LEVEL=INFO
   WORKING_CRS=EPSG:4326
   ```

5. **Run Database Migrations (PostgreSQL/PostGIS only):**
   If connected to a PostgreSQL instance:
   ```bash
   alembic upgrade head
   ```

6. **Seed the Database with Pilot Demo Data:**
   Populate users, 3D property hierarchy, observations, topology conflicts, and legal land records:
   ```bash
   python -m app.seeds.seed_demo_data
   ```

7. **Start the Backend API Server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

### B. Frontend Application Setup (React / Vite / TypeScript)

1. **Open a new terminal and navigate to the frontend directory:**
   ```bash
   cd src/frontend
   ```

2. **Install Node.js dependencies:**
   ```bash
   npm install
   ```

3. **Start the Vite Development Server:**
   ```bash
   npm run dev
   ```
   The UI will launch on `http://localhost:5173`. It automatically connects to the backend running on `http://localhost:8000`.

---

## 4. Environment Variables Configuration Reference

| Variable Name | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+psycopg://cadastral:cadastral_dev_only@localhost:5432/cadastral` | SQLAlchemy connection string (PostGIS or SQLite) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis instance for rate limiting and queues |
| `SECRET_KEY` | `CHANGE-ME-IN-PRODUCTION` | Cryptographic secret for signing JWT tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | JWT token lifespan in minutes (default: 8 hours) |
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `WORKING_CRS` | `EPSG:4326` | Standardized geodetic coordinate reference system |
| `OBJECT_STORE_ENDPOINT` | `""` | Optional S3/MinIO endpoint for evidence blob storage |
| `OBJECT_STORE_BUCKET` | `cadastral-evidence` | S3 bucket name for raw survey archives |

---

## 5. Seeding Demo Data & Initial Credentials

The system includes pre-configured government user accounts for testing role-based access control:

| Role | Username | Password | Key Permissions |
| :--- | :--- | :--- | :--- |
| **Verifying Officer** | `officer_sharma` | `DemoPass123!` | Authoritative verification, reject with notes, unmasked PII view, conflict resolution |
| **Field Surveyor** | `surveyor_verma` | `DemoPass123!` | Ingestion file uploads, draft spatial submissions |
| **Public Viewer** | `citizen_patel` | `DemoPass123!` | Read-only access to approved 2D/3D layers; owner PII masked |
| **Administrator** | `admin_cadastre` | `DemoPass123!` | System configuration, topology batch executions, audit review |

### Quick Role-Switching in UI:
In the top-right header of the web portal, use the **Active Role** dropdown to switch roles instantly via the `/api/v1/auth/quick-token` endpoint.

---

## 6. Running Verification & Automated Tests

### Backend Test Suite (pytest)
Run the complete suite of 117+ unit and integration tests (executes in < 3 seconds using an isolated in-memory test database):
```bash
cd src/backend
python -m pytest tests/ -v
```

To run a specific test suite:
```bash
# Deterministic topology rules (VR-01 through VR-09)
python -m pytest tests/test_topology_validation.py -v

# Production security headers, rate limiting, and PII redaction
python -m pytest tests/test_production_hardening.py -v

# Legal land registry linkage and audit logging
python -m pytest tests/test_legal_linkage.py -v
```

### Frontend Typecheck & Production Build
Validate TypeScript typings and build minified production bundles:
```bash
cd src/frontend
npm run build
```

---

## 7. Production Hardening Checklist

When deploying to a production municipal or cloud environment:
1. **Set Strong Secrets**: Generate a 256-bit cryptographically random `SECRET_KEY`.
2. **Enable TLS / HTTPS**: Front the application with Nginx or AWS ALB with TLS 1.3.
3. **Database Pooling**: Ensure PostgreSQL has `shared_buffers` and `work_mem` configured for PostGIS spatial queries.
4. **Regular Backups**: Follow [`docs/BACKUP_RESTORE.md`](BACKUP_RESTORE.md) for automated WAL archiving and daily pg_dump schedules.
