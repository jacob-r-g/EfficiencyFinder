"""Chunked file uploads, kept small enough to pass Cloudflare's body limit."""

from fastapi import APIRouter, HTTPException, Query, Request

from web.backend.store import Store, StoreError

router = APIRouter()


def _store(request: Request) -> Store:
    return request.app.state.store


@router.post("/api/uploads")
def create_upload(request: Request):
    store = _store(request)
    store.expire()
    return {"upload_id": store.new_upload_id()}


@router.put("/api/uploads/{upload_id}/files/{filename}")
async def put_chunk(
    request: Request,
    upload_id: str,
    filename: str,
    chunk: int = Query(..., ge=0),
    chunks: int = Query(..., ge=1),
):
    data = await request.body()
    try:
        assembled = _store(request).write_chunk(
            upload_id, filename, chunk, chunks, data
        )
    except StoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"assembled": assembled}
