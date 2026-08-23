"""Background QThread that runs the analysis pipeline."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QThread, Signal

from core.parsing import FastaValidationError, load_reference_set
from core.pipeline import SampleResult, run_batch
from core.settings import PipelineSettings


class RunWorker(QThread):
    progress = Signal(int, int, str, str, int, int)  # i, n, sample, stage, stage_i, stage_n
    sample_finished = Signal(object)  # SampleResult
    batch_finished = Signal(object)  # BatchResult
    failed = Signal(str, str, bool)  # message, traceback, is_validation_error

    def __init__(
        self,
        fasta_path: str,
        fastq_paths: list[str],
        settings: PipelineSettings,
        parent=None,
    ):
        super().__init__(parent)
        self._fasta_path = fasta_path
        self._fastq_paths = list(fastq_paths)
        self._settings = settings

    def run(self) -> None:
        try:
            ref_set = load_reference_set(self._fasta_path, flank=self._settings.flank)
        except FastaValidationError as exc:
            self.failed.emit(str(exc), "", True)
            return
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc(), False)
            return

        try:
            result = run_batch(
                self._fastq_paths,
                ref_set,
                self._settings,
                progress_callback=self._on_progress,
                sample_callback=self._on_sample,
            )
        except Exception as exc:
            self.failed.emit(str(exc), traceback.format_exc(), False)
            return
        self.batch_finished.emit(result)

    def _on_progress(
        self,
        i: int,
        n: int,
        sample_name: str,
        *,
        stage: str = "",
        stage_i: int = 0,
        stage_n: int = 0,
    ) -> None:
        self.progress.emit(i, n, sample_name, stage, stage_i, stage_n)

    def _on_sample(self, sample: SampleResult) -> None:
        self.sample_finished.emit(sample)
