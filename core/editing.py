"""WT/edited calling per guide and editing-efficiency summaries."""

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
STATUS_WT = "WT_intact"
STATUS_INSERTION = "edited_insertion"
STATUS_DEL_SMALL = "edited_deletion_small"
STATUS_DEL_LARGE = "edited_deletion_large"
STATUS_SUBSTITUTION = "edited_substitution"


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


def call_editing_status(
    classified_reads,
    amplicons,
    guides,
    guides_by_amplicon,
    settings: PipelineSettings | None = None,
) -> list[ReadGuideCall]:
    """Call WT/edited per guide.

    Coverage is per-guide: a read only needs to overlap that guide's local
    window. Missing flanks still produce an edit call (typically large
    deletion), so paired-guide dropouts between cuts are not discarded as
    not_sequenced. A guide the read never reaches stays not_sequenced.
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
        amp_len = len(amplicons[cr.amplicon])

        for gname in gnames:
            gi = guides[gname]
            w_start, w_end = _guide_window(gi, amp_len, s.coverage_margin)
            covered = (
                len(read_kmers & region_kmers(cr.amplicon, w_start, w_end))
                >= MIN_GUIDE_COVERAGE_KMERS
            )
            if not covered:
                calls.append(
                    ReadGuideCall(
                        cr.read_id, cr.amplicon, cr.orientation, gname, STATUS_NOT_SEQUENCED
                    )
                )
                continue

            lf, rf, tgt = gi.left_flank, gi.right_flank, gi.target
            lpos, lmm = find_best_match(lf, read_seq)
            rpos, rmm = find_best_match(rf, read_seq)
            l_ok = lpos is not None and lmm <= s.mismatch_thresh_flank
            r_ok = rpos is not None and rmm <= s.mismatch_thresh_flank

            if l_ok and r_ok:
                observed_gap = rpos - (lpos + len(lf))
                expected_gap = len(tgt)
                if observed_gap == expected_gap:
                    obs_target = read_seq[lpos + len(lf) : lpos + len(lf) + expected_gap]
                    tmm = sum(1 for a, b in zip(obs_target, tgt) if a != b)
                    status = (
                        STATUS_WT if tmm <= s.mismatch_thresh_target else STATUS_SUBSTITUTION
                    )
                elif observed_gap > expected_gap:
                    status = STATUS_INSERTION
                else:
                    status = STATUS_DEL_SMALL
            else:
                status = STATUS_DEL_LARGE

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
        covered = sum(v for k, v in t.items() if k != STATUS_NOT_SEQUENCED)
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
