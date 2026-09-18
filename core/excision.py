"""Paired-guide excision detection.

When two (or more) guides cut the same amplicon in one cell, NHEJ can join the
outer ends and drop the entire intervening fragment. On a spanning read that is
*not* two independent small indels, each guide's near-flanks fail to match, so
every guide is called inconclusive — the co-occurrence signature.

A confirmed excision additionally matches the leftmost left-flank to the
rightmost right-flank and finds a dropout spanning most of the expected
intervening distance. That size is real biology, not a concatemer artifact,
so it is *not* filtered by artifact_size_threshold.
"""

from collections import Counter
from dataclasses import dataclass
from math import nan
from statistics import median

from .editing import STATUS_DEL_LARGE, STATUS_INCONCLUSIVE, STATUS_NOT_SEQUENCED
from .matching import find_best_match
from .settings import PipelineSettings

# Co-occurrence signature for paired excision: local flanks failed at every guide
# (inconclusive) or legacy large-del calls.
_FLANK_FAIL_STATUSES = frozenset({STATUS_INCONCLUSIVE, STATUS_DEL_LARGE})


@dataclass
class ExcisionSummary:
    sample: str
    amplicon: str
    guides: str
    n_guides: int
    expected_dropout_bp: int
    n_spanning_reads: int
    n_simultaneous_large_del: int
    pct_simultaneous_large_del: float
    n_confirmed_excision: int
    pct_confirmed_excision: float
    median_excision_bp: float


@dataclass
class ExcisionSizeRow:
    sample: str
    amplicon: str
    excision_size_bp: int
    n_reads: int
    pct_of_confirmed: float


def _pct(numer: int, denom: int) -> float:
    return round(100.0 * numer / denom, 1) if denom else nan


def _ordered_guides(gnames, guides):
    return sorted(gnames, key=lambda g: (guides[g].cut_pos, guides[g].name))


def _expected_dropout_bp(left_gi, right_gi) -> int:
    """Distance between Cas9 cut sites (3 bp upstream of each PAM)."""
    return abs(right_gi.cut_pos - left_gi.cut_pos)


def _measure_dropout(read_seq, left_gi, right_gi, mismatch_thresh_flank: int):
    """Return measured outer-flank dropout bp, or None if flanks cannot be matched.

    Uses the WT distance between the leftmost left-flank and rightmost right-flank.
    For a clean cut-to-cut join this equals the Cas9 cut-to-cut distance.
    """
    lf, rf = left_gi.left_flank, right_gi.right_flank
    wt_flank_gap = right_gi.target_end - left_gi.target_start
    lpos, lmm = find_best_match(lf, read_seq)
    rpos, rmm = find_best_match(rf, read_seq)
    l_ok = lpos is not None and lmm <= mismatch_thresh_flank
    r_ok = rpos is not None and rmm <= mismatch_thresh_flank
    if not (l_ok and r_ok):
        return None
    if rpos < lpos + len(lf) - 5:
        return None
    observed_gap = rpos - (lpos + len(lf))
    return wt_flank_gap - observed_gap


def call_paired_excisions(
    classified_reads,
    editing_calls,
    guides,
    guides_by_amplicon,
    settings: PipelineSettings | None = None,
    sample: str = "",
) -> tuple[list[ExcisionSummary], list[ExcisionSizeRow]]:
    """Detect paired/multi-guide excision events per amplicon.

    An amplicon is only considered if it has 2+ guides. A spanning read is a
    paired-excision candidate when *every* guide on that amplicon has failed
    local flank placement (inconclusive / large-del). Confirmation requires an
    outer-flank dropout of at least
    max(min_excision_bp, expected_cut_to_cut * min_excision_fraction).
    Expected dropout is the distance between SpCas9 cut sites (3 bp upstream
    of each NGG PAM), not the full guide-span.
    """
    s = settings or PipelineSettings()

    # Walk classified reads and editing calls in lockstep (same order as
    # call_editing_status). Do not key on read_id — FASTQ IDs can collide.
    per_read: list[tuple[object, dict[str, str]]] = []
    call_i = 0
    for cr in classified_reads:
        if cr.amplicon is None:
            continue
        gnames = guides_by_amplicon.get(cr.amplicon, [])
        if not gnames:
            continue
        gst: dict[str, str] = {}
        for _ in gnames:
            if call_i >= len(editing_calls):
                break
            c = editing_calls[call_i]
            call_i += 1
            gst[c.guide] = c.status
        per_read.append((cr, gst))

    summaries: list[ExcisionSummary] = []
    size_rows: list[ExcisionSizeRow] = []

    for amp, gnames in guides_by_amplicon.items():
        if len(gnames) < 2:
            continue
        ordered = _ordered_guides(gnames, guides)
        left_gi = guides[ordered[0]]
        right_gi = guides[ordered[-1]]
        expected = _expected_dropout_bp(left_gi, right_gi)
        min_drop = max(s.min_excision_bp, int(expected * s.min_excision_fraction))

        spanning = 0
        both_large = 0
        confirmed_sizes: list[int] = []

        for cr, gst in per_read:
            if cr.amplicon != amp:
                continue
            if any(gst.get(g) == STATUS_NOT_SEQUENCED for g in ordered):
                continue
            spanning += 1
            if not all(gst.get(g) in _FLANK_FAIL_STATUSES for g in ordered):
                continue
            both_large += 1
            dropout = _measure_dropout(
                cr.oriented_seq, left_gi, right_gi, s.mismatch_thresh_flank
            )
            if dropout is not None and dropout >= min_drop:
                confirmed_sizes.append(dropout)

        size_counts = Counter(confirmed_sizes)
        n_conf = len(confirmed_sizes)
        for sz, n in sorted(size_counts.items(), key=lambda x: -x[1]):
            size_rows.append(
                ExcisionSizeRow(
                    sample=sample,
                    amplicon=amp,
                    excision_size_bp=sz,
                    n_reads=n,
                    pct_of_confirmed=_pct(n, n_conf),
                )
            )

        summaries.append(
            ExcisionSummary(
                sample=sample,
                amplicon=amp,
                guides=", ".join(ordered),
                n_guides=len(ordered),
                expected_dropout_bp=expected,
                n_spanning_reads=spanning,
                n_simultaneous_large_del=both_large,
                pct_simultaneous_large_del=_pct(both_large, spanning),
                n_confirmed_excision=n_conf,
                pct_confirmed_excision=_pct(n_conf, spanning),
                median_excision_bp=(
                    float(median(confirmed_sizes)) if confirmed_sizes else nan
                ),
            )
        )

    summaries.sort(key=lambda r: (r.sample, r.amplicon))
    return summaries, size_rows
