"""One-at-a-time analysis jobs. Poll for status; never hold an HTTP request open."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.parsing import FastaValidationError, load_reference_set
from core.pipeline import run_batch
from web.backend.combine import combine_fastq_files
from web.backend.serialize import jsonable
from web.backend.settings_body import settings_from_dict
from web.backend.store import Store, StoreError, safe_filename

ProgressFn = Callable[[int, int, str], None]
AnalyzeFn = Callable[[Path, list[Path], Any, ProgressFn], dict]


@dataclass
class JobState:
    id: str
    status: str
    progress: dict | None = None
    error: str | None = None
    is_validation: bool = False
    results: dict | None = None
    fasta_path: Path | None = field(default=None, repr=False)
    fastq_paths: list[Path] = field(default_factory=list, repr=False)
    settings: Any = field(default=None, repr=False)
    combine_fastqs: bool = False


def public_status(state: JobState) -> dict:
    return {
        "id": state.id,
        "status": state.status,
        "progress": state.progress,
        "error": state.error,
        "is_validation": state.is_validation,
    }


def default_analyze(
    fasta: Path, fastqs: list[Path], settings, on_progress: ProgressFn
) -> dict:
    ref = load_reference_set(str(fasta), flank=settings.flank)
    batch = run_batch(
        [str(p) for p in fastqs],
        ref,
        settings,
        progress_callback=on_progress,
    )
    data = jsonable(batch)
    data["samples"] = [
        {
            "sample_name": s.sample_name,
            "n_reads": s.n_reads,
            "n_assigned": s.n_assigned,
            "n_unassigned": s.n_unassigned,
        }
        for s in batch.samples
    ]
    return data


class JobManager:
    def __init__(self, store: Store, analyze: AnalyzeFn | None = None):
        self.store = store
        self.analyze = analyze or default_analyze
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._queue: list[str] = []
        threading.Thread(target=self._loop, daemon=True).start()

    def submit(
        self,
        upload_id: str,
        fasta: str,
        fastqs: list[str],
        settings: dict | None,
        combine_fastqs: bool = False,
    ) -> JobState:
        fasta_name = safe_filename(fasta)
        fastq_names = [safe_filename(n) for n in fastqs]
        if not fastq_names:
            raise StoreError("no FASTQ files")
        settings_obj = settings_from_dict(settings)
        assembled = {p.name: p for p in self.store.assembled_files(upload_id)}
        if fasta_name not in assembled:
            raise StoreError(f"missing FASTA: {fasta_name}")
        missing = [n for n in fastq_names if n not in assembled]
        if missing:
            raise StoreError(f"missing FASTQ: {missing[0]}")
        job_id = self.store.new_job_id()
        inputs = self.store.move_upload_into_job(upload_id, job_id)
        fasta_path = inputs / fasta_name
        fastq_paths = [inputs / n for n in fastq_names]
        state = JobState(
            id=job_id,
            status="queued",
            fasta_path=fasta_path,
            fastq_paths=fastq_paths,
            settings=settings_obj,
            combine_fastqs=combine_fastqs,
        )
        with self._cv:
            self._jobs[job_id] = state
            self._queue.append(job_id)
            self._cv.notify()
        return state

    def get(self, job_id: str) -> JobState:
        with self._lock:
            state = self._jobs.get(job_id)
        if state is None:
            raise StoreError("unknown job")
        return state

    def _loop(self) -> None:
        while True:
            with self._cv:
                while not self._queue:
                    self._cv.wait()
                job_id = self._queue.pop(0)
                state = self._jobs[job_id]
                state.status = "running"
                fasta = state.fasta_path
                fastqs = list(state.fastq_paths)
                settings = state.settings
                do_combine = state.combine_fastqs

            def on_progress(i: int, n: int, sample: str, _state=state) -> None:
                with self._lock:
                    _state.progress = {"i": i, "n": n, "sample": sample}

            try:
                if do_combine and len(fastqs) > 1:
                    on_progress(0, 1, "combining FASTQs")
                    combined = fasta.parent / "combined.fastq"
                    combine_fastq_files(fastqs, combined)
                    fastqs = [combined]
                results = self.analyze(fasta, fastqs, settings, on_progress)
                with self._lock:
                    state.results = results
                    state.status = "done"
            except FastaValidationError as exc:
                with self._lock:
                    state.status = "failed"
                    state.error = str(exc)
                    state.is_validation = True
            except Exception as exc:
                with self._lock:
                    state.status = "failed"
                    state.error = str(exc)
            finally:
                self.store.delete_job_inputs(job_id)
