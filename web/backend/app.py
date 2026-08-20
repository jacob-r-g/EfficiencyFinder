"""FastAPI entry point: health, uploads, and (later) jobs plus the React UI."""

from fastapi import FastAPI

from web.backend import job_routes, uploads
from web.backend.jobs import JobManager
from web.backend.store import Store


def create_app(store: Store | None = None, analyze=None) -> FastAPI:
    app = FastAPI(title="EfficiencyFinder")
    app.state.store = store or Store()
    app.state.jobs = JobManager(app.state.store, analyze=analyze)
    app.include_router(uploads.router)
    app.include_router(job_routes.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
