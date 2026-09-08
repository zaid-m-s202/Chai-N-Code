import hashlib
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db, SessionLocal
from app.models.ingestion_job import IngestionJob
from app.models.user import User
from app.schemas.ingestion import IngestionJobResponse
from app.ingestion.pipeline import process_ingestion

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def _run_background_ingestion(
    job_id: UUID,
    filename: str,
    file_content: bytes,
    file_format: str,
    operator_id: Optional[UUID],
    source_system: Optional[str],
):
    """Worker function executed asynchronously in background task."""
    db = SessionLocal()
    try:
        process_ingestion(
            db=db,
            job_id=job_id,
            filename=filename,
            file_content=file_content,
            file_format=file_format,
            operator_id=operator_id,
            source_system=source_system,
        )
    finally:
        db.close()


@router.post("/jobs", response_model=IngestionJobResponse, status_code=status.HTTP_201_CREATED)
async def create_ingestion_job(
    file: UploadFile = File(...),
    source_system: Optional[str] = Form(None),
    async_exec: bool = Query(True, description="Run ingestion as an asynchronous job (PRD FR-ING-02)"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a GeoJSON or CSV dataset to start an asynchronous, idempotent ingestion job."""
    content = await file.read()
    filename = file.filename or "uploaded_file"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ("geojson", "json", "csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '.{ext}'. Supported formats: .geojson, .json, .csv",
        )

    file_format = "geojson" if ext in ("geojson", "json") else "csv"
    file_hash = hashlib.sha256(content).hexdigest()

    # Idempotency check: if already completed with identical hash, return existing job
    existing_job = db.query(IngestionJob).filter(
        IngestionJob.file_hash == file_hash,
        IngestionJob.status == "COMPLETED",
    ).first()
    if existing_job:
        return existing_job

    # Create pending job
    job = IngestionJob(
        filename=filename,
        format=file_format,
        file_hash=file_hash,
        status="PENDING",
        operator_id=current_user.id if current_user else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if async_exec:
        # Asynchronous job execution per PRD FR-ING-02
        background_tasks.add_task(
            _run_background_ingestion,
            job_id=job.id,
            filename=filename,
            file_content=content,
            file_format=file_format,
            operator_id=current_user.id if current_user else None,
            source_system=source_system or f"upload_{filename}",
        )
        return job
    else:
        # Synchronous execution
        processed_job = process_ingestion(
            db=db,
            job_id=job.id,
            filename=filename,
            file_content=content,
            file_format=file_format,
            operator_id=current_user.id if current_user else None,
            source_system=source_system or f"upload_{filename}",
        )
        return processed_job


@router.get("/jobs", response_model=list[IngestionJobResponse])
def list_ingestion_jobs(db: Session = Depends(get_db)):
    """List recent ingestion jobs."""
    jobs = db.query(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(50).all()
    return jobs


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
def get_ingestion_job(job_id: UUID, db: Session = Depends(get_db)):
    """Retrieve ingestion job status and progress."""
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Ingestion job {job_id} not found")
    return job
