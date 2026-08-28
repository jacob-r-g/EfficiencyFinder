"""HTTP endpoints for starting a job and polling results."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from web.backend.jobs import JobManager, public_status
from web.backend.settings_body import SettingsError
from web.backend.store import Store, StoreError

router = APIRouter()


class JobCreate(BaseModel):
    upload_id: str
    fasta: str
    fastqs: list[str] = Field(min_length=1)
    settings: dict[str, int | float] = Field(default_factory=dict)
    combine_fastqs: bool = False


def _jobs(request: Request) -> JobManager:
    return request.app.state.jobs


@router.post("/api/jobs")
def create_job(body: JobCreate, request: Request):
    try:
        state = _jobs(request).submit(
            body.upload_id,
            body.fasta,
            body.fastqs,
            body.settings,
            combine_fastqs=body.combine_fastqs,
        )
    except (StoreError, SettingsError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return public_status(state)


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str, request: Request):
    try:
        state = _jobs(request).get(job_id)
    except StoreError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return public_status(state)


@router.get("/api/jobs/{job_id}/results")
def get_results(job_id: str, request: Request):
    try:
        state = _jobs(request).get(job_id)
    except StoreError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if state.status != "done":
        raise HTTPException(status_code=409, detail="results not ready")
    return state.results


@router.get("/api/jobs/{job_id}/unassigned/{sample_name}")
def download_unassigned(job_id: str, sample_name: str, request: Request):
    try:
        state = _jobs(request).get(job_id)
    except StoreError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if state.status != "done" or state.results is None:
        raise HTTPException(status_code=409, detail="results not ready")
    exports = state.results.get("unassigned_exports") or []
    entry = next((e for e in exports if e["sample_name"] == sample_name), None)
    if entry is None:
        raise HTTPException(status_code=404, detail="no unassigned reads for sample")
    path = request.app.state.store.job_path(job_id) / "exports" / entry["filename"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="export file missing")
    return FileResponse(
        path,
        media_type="application/x-fastq",
        filename=entry["filename"],
    )
