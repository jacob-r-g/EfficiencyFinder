"""CRISPR amplicon nanopore editing-efficiency analysis engine.

This package has no GUI / PySide6 imports and can be used standalone.
"""

from .settings import PipelineSettings
from .parsing import (
    FastaValidationError,
    GuideInfo,
    ReferenceSet,
    load_reference_set,
    parse_fasta,
    parse_fastq,
    revcomp,
)
from .pipeline import BatchResult, SampleResult, run_batch, run_single_sample

__all__ = [
    "PipelineSettings",
    "FastaValidationError",
    "GuideInfo",
    "ReferenceSet",
    "load_reference_set",
    "parse_fasta",
    "parse_fastq",
    "revcomp",
    "BatchResult",
    "SampleResult",
    "run_batch",
    "run_single_sample",
]
