"""On-disk upload and job directories under a configurable root."""

from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
MAX_NAME = 200
MAX_CHUNK_BYTES = 8 * 1024 * 1024
UPLOAD_TTL_S = 3600
RESULT_TTL_S = 3600
DEFAULT_ROOT = Path(os.environ.get("EFFICIENCYFINDER_DATA", "/tmp/efficiencyfinder"))


class StoreError(ValueError):
    pass


def _require_id(value: str) -> str:
    if not UUID_RE.match(value):
        raise StoreError("invalid id")
    return value


def safe_filename(name: str) -> str:
    if "/" in name or "\\" in name or name in {".", ".."}:
        raise StoreError(f"invalid filename: {name!r}")
    if not name or len(name) > MAX_NAME or not SAFE_NAME.match(name):
        raise StoreError(f"invalid filename: {name!r}")
    return name


class Store:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root is not None else DEFAULT_ROOT
        self.uploads = self.root / "uploads"
        self.jobs = self.root / "jobs"
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.jobs.mkdir(parents=True, exist_ok=True)

    def new_upload_id(self) -> str:
        uid = str(uuid.uuid4())
        (self.uploads / uid / "chunks").mkdir(parents=True)
        (self.uploads / uid / "files").mkdir(parents=True)
        return uid

    def upload_path(self, upload_id: str) -> Path:
        path = self.uploads / _require_id(upload_id)
        if not path.is_dir():
            raise StoreError("unknown upload")
        return path

    def write_chunk(
        self,
        upload_id: str,
        filename: str,
        chunk_index: int,
        total_chunks: int,
        data: bytes,
    ) -> bool:
        """Write one chunk. Returns True once the file is fully assembled."""
        filename = safe_filename(filename)
        if total_chunks < 1 or chunk_index < 0 or chunk_index >= total_chunks:
            raise StoreError("invalid chunk index")
        if len(data) > MAX_CHUNK_BYTES:
            raise StoreError("chunk too large")

        base = self.upload_path(upload_id)
        chunk_dir = base / "chunks" / filename
        chunk_dir.mkdir(parents=True, exist_ok=True)
        meta_path = chunk_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            if meta.get("chunks") != total_chunks:
                raise StoreError("chunk count mismatch")
        else:
            meta_path.write_text(json.dumps({"chunks": total_chunks}))
        (chunk_dir / f"{chunk_index:06d}").write_bytes(data)

        parts = [chunk_dir / f"{i:06d}" for i in range(total_chunks)]
        if not all(p.is_file() for p in parts):
            return False
        dest = base / "files" / filename
        with dest.open("wb") as out:
            for part in parts:
                out.write(part.read_bytes())
        shutil.rmtree(chunk_dir)
        return True

    def assembled_files(self, upload_id: str) -> list[Path]:
        files_dir = self.upload_path(upload_id) / "files"
        return sorted(p for p in files_dir.iterdir() if p.is_file())

    def new_job_id(self) -> str:
        jid = str(uuid.uuid4())
        (self.jobs / jid).mkdir(parents=True)
        return jid

    def job_path(self, job_id: str) -> Path:
        path = self.jobs / _require_id(job_id)
        if not path.is_dir():
            raise StoreError("unknown job")
        return path

    def move_upload_into_job(self, upload_id: str, job_id: str) -> Path:
        dest = self.job_path(job_id) / "inputs"
        src = self.upload_path(upload_id) / "files"
        shutil.move(str(src), str(dest))
        shutil.rmtree(self.upload_path(upload_id), ignore_errors=True)
        return dest

    def delete_job_inputs(self, job_id: str) -> None:
        inputs = self.job_path(job_id) / "inputs"
        if inputs.exists():
            shutil.rmtree(inputs)

    def expire(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        for path in self.uploads.iterdir():
            if path.is_dir() and now - path.stat().st_mtime > UPLOAD_TTL_S:
                shutil.rmtree(path, ignore_errors=True)
        for path in self.jobs.iterdir():
            if path.is_dir() and now - path.stat().st_mtime > RESULT_TTL_S:
                shutil.rmtree(path, ignore_errors=True)
