"""FastAPI entry point: health, uploads, jobs, and the built React UI."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from web.backend import job_routes, uploads
from web.backend.jobs import JobManager
from web.backend.store import Store

DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def _mount_frontend(app: FastAPI) -> None:
    if not DIST.is_dir():
        return
    assets = DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    def index():
        return FileResponse(DIST / "index.html")

    @app.get("/{path:path}")
    def spa(path: str):
        candidate = (DIST / path).resolve()
        if path and candidate.is_file() and DIST in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")


def create_app(store: Store | None = None, analyze=None) -> FastAPI:
    app = FastAPI(title="EfficiencyFinder")
    app.state.store = store or Store()
    app.state.jobs = JobManager(app.state.store, analyze=analyze)
    app.include_router(uploads.router)
    app.include_router(job_routes.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    _mount_frontend(app)
    return app


app = create_app()
