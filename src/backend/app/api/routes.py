"""API v1 master router aggregating all domain sub-routers."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.properties import router as properties_router
from app.api.ingestion import router as ingestion_router
from app.api.conflicts import router as conflicts_router
from app.api.search import router as search_router
from app.api.map_objects import router as map_router
from app.api.analysis import router as analysis_router
from app.api.legal import router as legal_router
from app.api.audit import router as audit_router
from app.api.export import router as export_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(properties_router)
router.include_router(ingestion_router)
router.include_router(conflicts_router)
router.include_router(search_router)
router.include_router(map_router)
router.include_router(analysis_router)
router.include_router(legal_router)
router.include_router(audit_router)
router.include_router(export_router)
