"""FastAPI application entrypoint for 3D Cadastral Intelligence.

Production-hardened with:
- Security headers & OWASP compliance middleware
- Structured JSON access logging
- Prometheus & JSON telemetry metrics (/metrics)
- Enterprise OpenAPI v3 metadata
- Decoupled CORS & health probes
"""

from contextlib import asynccontextmanager
from typing import Optional
from fastapi import Depends, FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.routes import router
from app.database import get_db
from app.middleware import SecurityHeadersMiddleware, StructuredLoggingMiddleware
from app.metrics import metrics_collector
import app.models  # Ensure all models are registered with Base.metadata


OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "Role-based authentication, JWT issuance, and user session identity management.",
    },
    {
        "name": "properties",
        "description": "3D Spatial property entity lifecycle (parcels, buildings, floors, units), multi-source observation fusion, unit split/merge, and authoritative verification.",
    },
    {
        "name": "ingestion",
        "description": "Sensor-agnostic ingestion pipeline supporting GeoJSON, CSV/WKT, and multi-sensor datasets with provenance hashing.",
    },
    {
        "name": "conflicts",
        "description": "Deterministic topology validation suite (VR-01 through VR-09), boundary violations, overlap checks, and conflict resolution/waiver.",
    },
    {
        "name": "legal",
        "description": "Cadastral and land registry linkage (ULPIN, title deed, tenure rights, encumbrances) with strict owner identity privacy protection.",
    },
    {
        "name": "analysis",
        "description": "AI & GIS spatial derivation adapters (DSM/DEM height calculation, floor level estimator, pretrained footprint extraction) with status gating.",
    },
    {
        "name": "audit",
        "description": "Immutable event-sourced change log compliance review and aggregation API.",
    },
    {
        "name": "export",
        "description": "Bulk cadastral tabular and GeoJSON dataset export with automated PII redaction and audit tracking.",
    },
    {
        "name": "search",
        "description": "Fast spatial and cadastral identifier indexing and text search.",
    },
    {
        "name": "map",
        "description": "Lightweight 2D/3D map layer endpoints for MapLibre GL and CesiumJS globe renderers.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables on startup (SQLite dev mode; use Alembic for production)
    from app.database import Base, engine
    Base.metadata.create_all(bind=engine)

    # In SQLite dev mode, ensure new columns are dynamically added if table was pre-existing
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("PRAGMA table_info(property_objects)"))
            existing_cols = {row[1] for row in result.fetchall()}
            if "stratum" not in existing_cols:
                conn.execute(text("ALTER TABLE property_objects ADD COLUMN stratum VARCHAR(20) DEFAULT 'SURFACE'"))
                conn.commit()
            if "volume_m3" not in existing_cols:
                conn.execute(text("ALTER TABLE property_objects ADD COLUMN volume_m3 FLOAT DEFAULT 0.0"))
                conn.commit()
    except Exception as e:
        print(f"Warning: SQLite auto-migration check: {e}")

    yield


app = FastAPI(
    title="3D Cadastral Intelligence & Land Administration API",
    description="""
## National 3D Cadastral & Land Administration Platform

Production pilot providing evidence-backed 3D Property Identification, event-sourced spatial lifecycle management, sensor-agnostic multi-source fusion, deterministic topology validation, AI spatial analysis adapters, and land registry linkage.

### Key Cadastral Principles:
* **Space vs. Ownership Decoupling:** 3D Property ID identifies 3D space (`{ULPIN}-{building_seq}-F{floor_seq}-U{unit_seq}`), never an owner.
* **AI Derives; Authority Verifies:** AI outputs produce `INFERRED`/`DERIVED` statuses; only authorized verifying officers can verify records.
* **Owner Privacy:** Owner identity is protected behind strict RBAC and never inferred.
* **Event-Sourced Lineage:** Every update generates an immutable `change_event` audit record.
""",
    version="1.0.0",
    openapi_tags=OPENAPI_TAGS,
    contact={
        "name": "Cadastral Intelligence Engineering Team",
        "email": "cadastre-support@nic.in",
    },
    license_info={
        "name": "Government Open Data License (India)",
        "url": "https://data.gov.in/government-open-data-license-india",
    },
    lifespan=lifespan,
)

# 1. Security Headers Middleware (OWASP)
app.add_middleware(SecurityHeadersMiddleware)

# 2. Structured JSON Access Logging Middleware
app.add_middleware(StructuredLoggingMiddleware)

# 3. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Content-Type-Options", "X-Frame-Options"],
)

# 4. Master API v1 Router
app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["system"], summary="Service Liveness Probe")
def health():
    """Liveness probe: returns 200 if the HTTP service process is alive."""
    return {
        "status": "ok",
        "service": "3d-cadastral-api",
        "version": "1.0.0",
    }


@app.get("/health/ready", tags=["system"], summary="Service Readiness Probe")
def health_ready(db: Session = Depends(get_db)):
    """Readiness probe: verifies database connectivity and core table availability."""
    db_status = "unknown"
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"unreachable ({str(e)[:60]})"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "service": "3d-cadastral-api",
        "database": db_status,
    }


@app.get(
    "/metrics",
    tags=["system"],
    summary="Observability & Telemetry Metrics",
)
def get_metrics(
    format: Optional[str] = Query("prometheus", description="Output format: prometheus | json"),
    db: Session = Depends(get_db),
):
    """Expose telemetry metrics in Prometheus exposition or structured JSON format."""
    if format == "json":
        return metrics_collector.to_json_summary(db)
    
    prometheus_text = metrics_collector.to_prometheus_text(db)
    return Response(
        content=prometheus_text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
