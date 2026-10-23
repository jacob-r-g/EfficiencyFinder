"""Paired-guide excision detection and efficiency promotion of large edits.

When two (or more) guides cut the same amplicon in one cell, NHEJ can join the
outer ends and drop the entire intervening fragment. On a spanning read that is
*not* two independent small indels, each guide's near-flanks fail to match, so
every guide is called inconclusive — the co-occurrence signature.

A confirmed excision additionally matches the leftmost left-flank to the
rightmost right-flank and finds a dropout spanning most of the expected
intervening distance. That size is real biology, not a concatemer artifact,
so it is *not* filtered by artifact_size_threshold.

promote_large_edits then upgrades confirmed dual-guide excisions and measurable
single-site large dropouts so they enter Efficiency pct_editing.
"""

from collections import Counter
from dataclasses import dataclass
from math import nan
from statistics import median

from .editing import (
    STATUS_DEL_LARGE,
    STATUS_EXCISION,
    STATUS_INCONCLUSIVE,
    STATUS_NOT_SEQUENCED,
    ReadGuideCall,
)
from .matching import find_best_match
from .settings import PipelineSettings

# Co-occurrence signature for paired excision: local flanks failed at every guide
# (inconclusive) or legacy large-del calls. Excision runs on pre-promote calls.
_FLANK_FAIL_STATUSES = frozenset({STATUS_INCONCLUSIVE, STATUS_DEL_LARGE})

# Outer anchors beyond near-flanks for single-guide large-deletion promotion.
_OUTER_OFFSET = 100


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


def _measure_outer_dropout(
    read_seq: str,
    amp_seq: str,
    gi,
    mismatch_thresh_flank: int,
    outer_offset: int = _OUTER_OFFSET,
) -> int | None:
    """Dropout using flanks placed outer_offset bp beyond the near-flanks.

    Returns measured deletion size (WT outer gap − observed), or None.
    """
    flank_len = len(gi.left_flank)
    if flank_len < 1:
        return None
    l0 = max(0, gi.target_start - len(gi.left_flank) - outer_offset)
    l1 = l0 + flank_len
    r1 = min(len(amp_seq), gi.target_end + len(gi.right_flank) + outer_offset)
    r0 = r1 - flank_len
    if l1 > r0 or l1 > len(amp_seq) or r0 < 0:
        return None
    lf = amp_seq[l0:l1]
    rf = amp_seq[r0:r1]
    if len(lf) != flank_len or len(rf) != flank_len:
        return None
    wt_gap = r0 - l1
    lpos, lmm = find_best_match(lf, read_seq)
    rpos, rmm = find_best_match(rf, read_seq)
    l_ok = lpos is not None and lmm <= mismatch_thresh_flank
    r_ok = rpos is not None and rmm <= mismatch_thresh_flank
    if not (l_ok and r_ok):
        return None
    if rpos < lpos + len(lf) - 5:
        return None
    observed_gap = rpos - (lpos + len(lf))
    return wt_gap - observed_gap


def _walk_per_read(classified_reads, editing_calls, guides_by_amplicon):
    """Lockstep walk of classified reads with their per-guide editing calls."""
    per_read: list[tuple[object, list[ReadGuideCall]]] = []
    call_i = 0
    for cr in classified_reads:
        if cr.amplicon is None:
            continue
        gnames = guides_by_amplicon.get(cr.amplicon, [])
        if not gnames:
            continue
        slice_calls: list[ReadGuideCall] = []
        for _ in gnames:
            if call_i >= len(editing_calls):
                break
            slice_calls.append(editing_calls[call_i])
            call_i += 1
        per_read.append((cr, slice_calls))
    return per_read


def call_paired_excisions(
    classified_reads,
    editing_calls,
    guides,
    guides_by_amplicon,
    settings: PipelineSettings | None = None,
    sample: str = "",
) -> tuple[list[ExcisionSummary], list[ExcisionSizeRow], set[int]]:
    """Detect paired/multi-guide excision events per amplicon.

    An amplicon is only considered if it has 2+ guides. A spanning read is a
    paired-excision candidate when *every* guide on that amplicon has failed
    local flank placement (inconclusive / large-del). Confirmation requires an
    outer-flank dropout of at least
    max(min_excision_bp, expected_cut_to_cut * min_excision_fraction).
    Expected dropout is the distance between SpCas9 cut sites (3 bp upstream
    of each NGG PAM), not the full guide-span.

    Returns (summaries, size_rows, confirmed_cr_ids) where confirmed_cr_ids is
    a set of id(classified_read) for confirmed excision molecules. Callers must
    promote efficiency using those ids on a copy of the pre-promote calls so
    this tab keeps the co-occurrence signature.
    """
    s = settings or PipelineSettings()
    per_read = _walk_per_read(classified_reads, editing_calls, guides_by_amplicon)

    summaries: list[ExcisionSummary] = []
    size_rows: list[ExcisionSizeRow] = []
    confirmed_cr_ids: set[int] = set()

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

        for cr, slice_calls in per_read:
            if cr.amplicon != amp:
                continue
            gst = {c.guide: c.status for c in slice_calls}
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
                confirmed_cr_ids.add(id(cr))

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
    return summaries, size_rows, confirmed_cr_ids


def promote_large_edits(
    classified_reads,
    editing_calls: list[ReadGuideCall],
    amplicons,
    guides,
    guides_by_amplicon,
    confirmed_excision_ids: set[int],
    settings: PipelineSettings | None = None,
) -> list[ReadGuideCall]:
    """Promote evidence-backed large edits for Efficiency accounting.

    - Confirmed dual-guide excision reads → edited_excision on every guide.
    - Remaining single-site inconclusive with measurable outer-flank large
      dropout → edited_deletion_large.
    - On multi-guide amplicons where every sequenced guide is still
      inconclusive (excision not confirmed), do **not** promote via per-guide
      outer anchors — that would asymmetrically edit one guide and leave the
      other inconclusive on the same molecule. Leave them inconclusive.
    Unverified inconclusive is left unchanged (excluded from pct_editing).

    Mutates and returns the same call list. Run excision on the pre-promote
    statuses first so Paired excision is unchanged.
    """
    s = settings or PipelineSettings()
    per_read = _walk_per_read(classified_reads, editing_calls, guides_by_amplicon)

    for cr, slice_calls in per_read:
        if id(cr) in confirmed_excision_ids:
            for c in slice_calls:
                if c.status != STATUS_NOT_SEQUENCED:
                    c.status = STATUS_EXCISION
            continue

        sequenced = [c for c in slice_calls if c.status != STATUS_NOT_SEQUENCED]
        if (
            len(sequenced) >= 2
            and all(c.status == STATUS_INCONCLUSIVE for c in sequenced)
        ):
            # Co-occurrence without confirmed excision: keep symmetric.
            continue

        amp_seq = amplicons[cr.amplicon]
        for c in slice_calls:
            if c.status != STATUS_INCONCLUSIVE:
                continue
            gi = guides[c.guide]
            expected_local = max(gi.target_end - gi.target_start, 1)
            min_drop = max(
                s.min_excision_bp, int(expected_local * s.min_excision_fraction)
            )
            dropout = _measure_outer_dropout(
                cr.oriented_seq, amp_seq, gi, s.mismatch_thresh_flank
            )
            if dropout is not None and dropout >= min_drop:
                c.status = STATUS_DEL_LARGE

    return editing_calls
