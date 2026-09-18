"""WT/edited calling per guide and editing-efficiency summaries.

WT is cut-local: with both near-flanks placed, the nuclease-specific WT
window on the reference must appear intact between the flanks.
  Cas9: 3 bp upstream + 3 bp downstream of the blunt cut
  Cas12: spacer positions 16–23 (covers the staggered cuts)
Distal spacer noise outside that window does not count as editing. Failed
flank placement is inconclusive (excluded from pct_editing).
"""

from collections import Counter, defaultdict
from dataclasses import dataclass

from .classify import kmer_set
from .matching import find_best_match, kmers_in_ref_range
from .settings import PipelineSettings

FLANK = 25
MISMATCH_THRESH_FLANK = 4
MISMATCH_THRESH_TARGET = 4
K_SPAN = 15
COVERAGE_MARGIN = 40
MIN_GUIDE_COVERAGE_KMERS = 2

STATUS_NOT_SEQUENCED = "not_sequenced"
STATUS_INCONCLUSIVE = "inconclusive"
STATUS_WT = "WT_intact"
STATUS_INSERTION = "edited_insertion"
STATUS_DEL_SMALL = "edited_deletion_small"
STATUS_DEL_LARGE = "edited_deletion_large"
STATUS_SUBSTITUTION = "edited_substitution"

# Statuses that do not enter the pct_editing denominator.
_EXCLUDED_FROM_SPANNING = frozenset({STATUS_NOT_SEQUENCED, STATUS_INCONCLUSIVE})


@dataclass
class ReadGuideCall:
    read_id: str
    amplicon: str
    orientation: str
    guide: str
    status: str


def _guide_window(gi, amp_len: int, coverage_margin: int) -> tuple[int, int]:
    """[start, end) window around one guide's flanks + margin."""
    start = max(0, gi.target_start - len(gi.left_flank) - coverage_margin)
    end = min(amp_len, gi.target_end + len(gi.right_flank) + coverage_margin)
    return start, end


def _call_with_flanks(
    read_seq: str,
    amp_seq: str,
    gi,
    *,
    mismatch_thresh_flank: int,
) -> str:
    """Classify one guide when the read covers its local window."""
    lf, rf = gi.left_flank, gi.right_flank
    lpos, lmm = find_best_match(lf, read_seq)
    rpos, rmm = find_best_match(rf, read_seq)
    l_ok = lpos is not None and lmm <= mismatch_thresh_flank
    r_ok = rpos is not None and rmm <= mismatch_thresh_flank
    if not (l_ok and r_ok):
        return STATUS_INCONCLUSIVE

    if gi.wt_start < 0 or gi.wt_end > len(amp_seq) or gi.wt_start >= gi.wt_end:
        return STATUS_INCONCLUSIVE
    ref_win = amp_seq[gi.wt_start : gi.wt_end]

    # Sequence between the placed flanks (inclusive of the target region).
    between = read_seq[lpos + len(lf) : rpos]
    if ref_win in between:
        return STATUS_WT

    observed_gap = rpos - (lpos + len(lf))
    expected_gap = gi.target_end - gi.target_start
    if observed_gap > expected_gap:
        return STATUS_INSERTION
    if observed_gap < expected_gap:
        return STATUS_DEL_SMALL
    return STATUS_SUBSTITUTION


def call_editing_status(
    classified_reads,
    amplicons,
    guides,
    guides_by_amplicon,
    settings: PipelineSettings | None = None,
) -> list[ReadGuideCall]:
    """Call WT/edited per guide using the nuclease WT window on GuideInfo.

    Coverage is per-guide. WT requires both near-flanks and an exact match to
    the reference WT window (Cas9 cut ±3 bp, or Cas12 spacer 16–23). Missing
    flanks are inconclusive. A guide the read never reaches stays not_sequenced.
    """
    s = settings or PipelineSettings()
    region_kmer_cache = {}

    def region_kmers(amp, start, end):
        key = (amp, start, end)
        if key not in region_kmer_cache:
            region_kmer_cache[key] = kmers_in_ref_range(
                amplicons[amp], start, end, k=s.k_span
            )
        return region_kmer_cache[key]

    calls = []
    for cr in classified_reads:
        if cr.amplicon is None:
            continue
        gnames = guides_by_amplicon.get(cr.amplicon, [])
        if not gnames:
            continue

        read_seq = cr.oriented_seq
        read_kmers = kmer_set(read_seq, k=s.k_span)
        amp_seq = amplicons[cr.amplicon]
        amp_len = len(amp_seq)

        for gname in gnames:
            gi = guides[gname]
            w_start, w_end = _guide_window(gi, amp_len, s.coverage_margin)
            covered = (
                len(read_kmers & region_kmers(cr.amplicon, w_start, w_end))
                >= MIN_GUIDE_COVERAGE_KMERS
            )
            if not covered:
                status = STATUS_NOT_SEQUENCED
            else:
                status = _call_with_flanks(
                    read_seq,
                    amp_seq,
                    gi,
                    mismatch_thresh_flank=s.mismatch_thresh_flank,
                )
            calls.append(
                ReadGuideCall(cr.read_id, cr.amplicon, cr.orientation, gname, status)
            )
    return calls


@dataclass
class GuideEfficiency:
    sample: str
    guide: str
    amplicon: str
    total_amplicon_reads: int
    reads_spanning_target: int
    not_sequenced: int
    inconclusive: int
    wt_unedited: int
    edited: int
    edited_insertion: int
    edited_deletion_small: int
    edited_deletion_large: int
    edited_substitution: int
    pct_editing: float


def summarize_efficiency(
    calls, guides, amp_read_counts, sample: str = ""
) -> list[GuideEfficiency]:
    tally = defaultdict(Counter)
    for c in calls:
        tally[c.guide][c.status] += 1
    out = []
    for gname, gi in guides.items():
        t = tally[gname]
        total = amp_read_counts.get(gi.amplicon, 0)
        covered = sum(v for k, v in t.items() if k not in _EXCLUDED_FROM_SPANNING)
        wt = t[STATUS_WT]
        edited = covered - wt
        pct = 100 * edited / covered if covered else float("nan")
        out.append(
            GuideEfficiency(
                sample=sample,
                guide=gname,
                amplicon=gi.amplicon,
                total_amplicon_reads=total,
                reads_spanning_target=covered,
                not_sequenced=t[STATUS_NOT_SEQUENCED],
                inconclusive=t[STATUS_INCONCLUSIVE],
                wt_unedited=wt,
                edited=edited,
                edited_insertion=t[STATUS_INSERTION],
                edited_deletion_small=t[STATUS_DEL_SMALL],
                edited_deletion_large=t[STATUS_DEL_LARGE],
                edited_substitution=t[STATUS_SUBSTITUTION],
                pct_editing=round(pct, 1) if covered else float("nan"),
            )
        )
    return out
