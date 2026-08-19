"""Tunable pipeline thresholds. Defaults match the validated analysis."""

from dataclasses import dataclass


@dataclass
class PipelineSettings:
    # classification
    k_classify: int = 17
    min_classify_score: int = 15
    # editing efficiency
    flank: int = 25
    mismatch_thresh_flank: int = 4
    mismatch_thresh_target: int = 4
    k_span: int = 15
    coverage_margin: int = 40
    # indel sizing
    mismatch_fraction: float = 0.18
    max_extra: int = 400
    artifact_size_threshold: int = 100
    # allele calling
    min_allele_reads: int = 3
    merge_edit_dist: int = 2
