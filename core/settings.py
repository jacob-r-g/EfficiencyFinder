"""Tunable pipeline thresholds. Defaults match the validated analysis."""

from dataclasses import dataclass


@dataclass
class PipelineSettings:
    # nuclease geometry (Cas9: NGG + cut±3; Cas12: 4 bp PAM from guide + spacer 16–23 WT)
    nuclease: str = "cas9"
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
    # paired-guide excision
    min_excision_bp: int = 30
    min_excision_fraction: float = 0.4
