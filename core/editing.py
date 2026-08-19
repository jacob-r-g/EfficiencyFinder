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


def _amplicon_outer_brackets(amplicons, guides_by_amplicon, guides, coverage_margin: int):
    brackets = {}
    for amp, gnames in guides_by_amplicon.items():
        if not gnames:
            continue
        starts = [guides[g].target_start - len(guides[g].left_flank) for g in gnames]
        ends = [guides[g].target_end + len(guides[g].right_flank) for g in gnames]
        brackets[amp] = (min(starts) - coverage_margin, max(ends) + coverage_margin)
    return brackets


def call_editing_status(
    classified_reads,
    amplicons,
    guides,
    guides_by_amplicon,
    settings: PipelineSettings | None = None,
) -> list[ReadGuideCall]:
    s = settings or PipelineSettings()
    outer_brackets = _amplicon_outer_brackets(
        amplicons, guides_by_amplicon, guides, s.coverage_margin
    )
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
        ob_start, ob_end = outer_brackets[cr.amplicon]
        covered = (
            len(read_kmers & region_kmers(cr.amplicon, ob_start, ob_start + s.coverage_margin)) >= 2
            and len(read_kmers & region_kmers(cr.amplicon, ob_end - s.coverage_margin, ob_end)) >= 2
        )

        for gname in gnames:
            if not covered:
                calls.append(
                    ReadGuideCall(
                        cr.read_id, cr.amplicon, cr.orientation, gname, STATUS_NOT_SEQUENCED
                    )
                )
                continue

            gi = guides[gname]
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
