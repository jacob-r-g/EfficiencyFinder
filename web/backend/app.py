"""FastAPI entry point: health, uploads, and (later) jobs plus the React UI."""

from fastapi import FastAPI

from web.backend import uploads
from web.backend.store import Store


def create_app(store: Store | None = None) -> FastAPI:
    app = FastAPI(title="EfficiencyFinder")
    app.state.store = store or Store()
    app.include_router(uploads.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
