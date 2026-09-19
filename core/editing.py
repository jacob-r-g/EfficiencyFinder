"""WT/edited calling per guide and editing-efficiency summaries.

WT is cut-local: with both near-flanks placed, the nuclease-specific WT
window on the reference must appear intact between the flanks.
  Cas9: 3 bp upstream + 3 bp downstream of the blunt cut
  Cas12: spacer positions 16–23 (covers the staggered cuts)
Distal spacer noise outside that window does not count as editing. Failed
flank placement is inconclusive (excluded from pct_editing).
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .classify import kmer_set
from .matching import find_best_match, kmers_in_ref_range
from .nuclease import NUCLEASE_CAS9, normalize_nuclease
from .settings import PipelineSettings

FLANK = 25
MISMATCH_THRESH_FLANK = 4
MISMATCH_THRESH_TARGET = 4
K_SPAN = 15
COVERAGE_MARGIN = 40
MIN_GUIDE_COVERAGE_KMERS = 2

# Caps for the Efficiency Inspect panel (per guide × sample).
MAX_INSPECT_EDITED = 40
MAX_INSPECT_WT = 20
MAX_INSPECT_INCONCLUSIVE = 15

STATUS_NOT_SEQUENCED = "not_sequenced"
STATUS_INCONCLUSIVE = "inconclusive"
STATUS_WT = "WT_intact"
STATUS_INSERTION = "edited_insertion"
STATUS_DEL_SMALL = "edited_deletion_small"
STATUS_DEL_LARGE = "edited_deletion_large"
STATUS_SUBSTITUTION = "edited_substitution"

# Statuses that do not enter the pct_editing denominator.
_EXCLUDED_FROM_SPANNING = frozenset({STATUS_NOT_SEQUENCED, STATUS_INCONCLUSIVE})
_EDITED_STATUSES = frozenset(
    {
        STATUS_INSERTION,
        STATUS_DEL_SMALL,
        STATUS_DEL_LARGE,
        STATUS_SUBSTITUTION,
    }
)


@dataclass
class ReadGuideCall:
    read_id: str
    amplicon: str
    orientation: str
    guide: str
    status: str


@dataclass
class InspectExample:
    """One read shown in the Efficiency Inspect panel."""

    read_id: str
    orientation: str
    status: str
    between: str
    observed_gap: int
    expected_gap: int
    wt_window_found: bool
    note: str


@dataclass
class GuideInspect:
    """Reference annotations + capped read examples for one sample × guide."""

    sample: str
    guide: str
    amplicon: str
    nuclease: str
    strand: str
    ref_local: str
    left_flank_len: int
    right_flank_len: int
    target_len: int
    # Coordinates are 0-based offsets into ref_local.
    pam_start: int
    pam_end: int
    spacer_start: int
    spacer_end: int
    wt_start: int
    wt_end: int
    cut_offset: int
    ref_wt_window: str
    examples: list[InspectExample] = field(default_factory=list)
    n_edited_total: int = 0
    n_wt_total: int = 0
    n_inconclusive_total: int = 0


def _guide_window(gi, amp_len: int, coverage_margin: int) -> tuple[int, int]:
    """[start, end) window around one guide's flanks + margin."""
    start = max(0, gi.target_start - len(gi.left_flank) - coverage_margin)
    end = min(amp_len, gi.target_end + len(gi.right_flank) + coverage_margin)
    return start, end


def _annotation_offsets(gi, nuclease: str) -> tuple[int, int, int, int]:
    """PAM and spacer [start, end) offsets relative to ref_local."""
    local0 = gi.target_start - len(gi.left_flank)
    nuclease = normalize_nuclease(nuclease)
    if nuclease == NUCLEASE_CAS9:
        pam_len = 3
        if gi.strand == "+":
            pam_s, pam_e = gi.target_end - pam_len, gi.target_end
            sp_s, sp_e = gi.target_start, gi.target_end - pam_len
        else:
            pam_s, pam_e = gi.target_start, gi.target_start + pam_len
            sp_s, sp_e = gi.target_start + pam_len, gi.target_end
    else:
        pam_len = 4
        if gi.strand == "+":
            pam_s, pam_e = gi.target_start, gi.target_start + pam_len
            sp_s, sp_e = gi.target_start + pam_len, gi.target_end
        else:
            pam_s, pam_e = gi.target_end - pam_len, gi.target_end
            sp_s, sp_e = gi.target_start, gi.target_end - pam_len
    return pam_s - local0, pam_e - local0, sp_s - local0, sp_e - local0


def _status_note(status: str, observed_gap: int, expected_gap: int) -> str:
    if status == STATUS_WT:
        return "WT window present between flanks"
    if status == STATUS_INCONCLUSIVE:
        return "Near-flank placement failed"
    if status == STATUS_INSERTION:
        return f"Gap {observed_gap} bp > expected {expected_gap} bp (insertion)"
    if status == STATUS_DEL_SMALL:
        return f"Gap {observed_gap} bp < expected {expected_gap} bp (deletion)"
    if status == STATUS_SUBSTITUTION:
        return f"Gap matches expected {expected_gap} bp but WT window disrupted"
    return status


def _call_with_flanks(
    read_seq: str,
    amp_seq: str,
    gi,
    *,
    mismatch_thresh_flank: int,
) -> tuple[str, InspectExample | None]:
    """Classify one guide when the read covers its local window."""
    lf, rf = gi.left_flank, gi.right_flank
    lpos, lmm = find_best_match(lf, read_seq)
    rpos, rmm = find_best_match(rf, read_seq)
    l_ok = lpos is not None and lmm <= mismatch_thresh_flank
    r_ok = rpos is not None and rmm <= mismatch_thresh_flank
    if not (l_ok and r_ok):
        return STATUS_INCONCLUSIVE, None

    if gi.wt_start < 0 or gi.wt_end > len(amp_seq) or gi.wt_start >= gi.wt_end:
        return STATUS_INCONCLUSIVE, None
    ref_win = amp_seq[gi.wt_start : gi.wt_end]

    between = read_seq[lpos + len(lf) : rpos]
    observed_gap = rpos - (lpos + len(lf))
    expected_gap = gi.target_end - gi.target_start
    wt_found = ref_win in between

    if wt_found:
        status = STATUS_WT
    elif observed_gap > expected_gap:
        status = STATUS_INSERTION
    elif observed_gap < expected_gap:
        status = STATUS_DEL_SMALL
    else:
        status = STATUS_SUBSTITUTION

    example = InspectExample(
        read_id="",
        orientation="",
        status=status,
        between=between,
        observed_gap=observed_gap,
        expected_gap=expected_gap,
        wt_window_found=wt_found,
        note=_status_note(status, observed_gap, expected_gap),
    )
    return status, example


def _empty_guide_inspect(sample: str, gi, nuclease: str, amp_seq: str) -> GuideInspect:
    local0 = gi.target_start - len(gi.left_flank)
    local1 = gi.target_end + len(gi.right_flank)
    ref_local = amp_seq[local0:local1]
    pam_s, pam_e, sp_s, sp_e = _annotation_offsets(gi, nuclease)
    return GuideInspect(
        sample=sample,
        guide=gi.name,
        amplicon=gi.amplicon,
        nuclease=normalize_nuclease(nuclease),
        strand=gi.strand,
        ref_local=ref_local,
        left_flank_len=len(gi.left_flank),
        right_flank_len=len(gi.right_flank),
        target_len=gi.target_end - gi.target_start,
        pam_start=pam_s,
        pam_end=pam_e,
        spacer_start=sp_s,
        spacer_end=sp_e,
        wt_start=gi.wt_start - local0,
        wt_end=gi.wt_end - local0,
        cut_offset=gi.cut_pos - local0,
        ref_wt_window=amp_seq[gi.wt_start : gi.wt_end],
    )


def call_editing_status(
    classified_reads,
    amplicons,
    guides,
    guides_by_amplicon,
    settings: PipelineSettings | None = None,
    sample: str = "",
) -> tuple[list[ReadGuideCall], list[GuideInspect]]:
    """Call WT/edited per guide; also build capped Inspect examples.

    Returns (calls, inspect_panels). Coverage is per-guide. WT requires both
    near-flanks and an exact match to the reference WT window.
    """
    s = settings or PipelineSettings()
    nuclease = normalize_nuclease(s.nuclease)
    region_kmer_cache = {}

    def region_kmers(amp, start, end):
        key = (amp, start, end)
        if key not in region_kmer_cache:
            region_kmer_cache[key] = kmers_in_ref_range(
                amplicons[amp], start, end, k=s.k_span
            )
        return region_kmer_cache[key]

    panels: dict[str, GuideInspect] = {
        gname: _empty_guide_inspect(sample, gi, nuclease, amplicons[gi.amplicon])
        for gname, gi in guides.items()
    }
    n_kept = {gname: {"edited": 0, "wt": 0, "inconclusive": 0} for gname in guides}

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
            example: InspectExample | None = None
            if not covered:
                status = STATUS_NOT_SEQUENCED
            else:
                status, example = _call_with_flanks(
                    read_seq,
                    amp_seq,
                    gi,
                    mismatch_thresh_flank=s.mismatch_thresh_flank,
                )
            calls.append(
                ReadGuideCall(cr.read_id, cr.amplicon, cr.orientation, gname, status)
            )

            panel = panels[gname]
            if status in _EDITED_STATUSES:
                panel.n_edited_total += 1
                if example is not None and n_kept[gname]["edited"] < MAX_INSPECT_EDITED:
                    example.read_id = cr.read_id
                    example.orientation = cr.orientation
                    panel.examples.append(example)
                    n_kept[gname]["edited"] += 1
            elif status == STATUS_WT:
                panel.n_wt_total += 1
                if example is not None and n_kept[gname]["wt"] < MAX_INSPECT_WT:
                    example.read_id = cr.read_id
                    example.orientation = cr.orientation
                    panel.examples.append(example)
                    n_kept[gname]["wt"] += 1
            elif status == STATUS_INCONCLUSIVE:
                panel.n_inconclusive_total += 1
                if n_kept[gname]["inconclusive"] < MAX_INSPECT_INCONCLUSIVE:
                    panel.examples.append(
                        InspectExample(
                            read_id=cr.read_id,
                            orientation=cr.orientation,
                            status=STATUS_INCONCLUSIVE,
                            between="",
                            observed_gap=0,
                            expected_gap=gi.target_end - gi.target_start,
                            wt_window_found=False,
                            note=_status_note(STATUS_INCONCLUSIVE, 0, 0),
                        )
                    )
                    n_kept[gname]["inconclusive"] += 1

    return calls, list(panels.values())


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
