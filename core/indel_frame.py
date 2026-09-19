"""Precise net indel size measurement + in-frame/frameshift classification.

Uses incremental anchor extension (start tight at 25bp, widen only if needed).
Do NOT replace this with a fixed wide anchor — that overcounts nanopore noise.
"""

from dataclasses import dataclass

from .matching import find_best_match

MISMATCH_FRACTION = 0.18  # max fraction of anchor length allowed to mismatch
MAX_EXTRA = 400  # cap on how far the anchor search will extend
ANCHOR_STEPS = (25, 50, 75, 100, 150, 200, 300, 400)
ARTIFACT_SIZE_THRESHOLD = 100  # net indel sizes beyond this are concatemer artifacts

# Pairwise alignment scores for allele display (allele vs WT target).
_ALIGN_MATCH = 2
_ALIGN_MISMATCH = -1
_ALIGN_GAP = -2


def extract_allele(
    read_seq,
    amp_seq,
    target_start,
    target_end,
    mismatch_fraction=MISMATCH_FRACTION,
    max_extra=MAX_EXTRA,
    anchor_steps=ANCHOR_STEPS,
):
    """Same incremental-anchor search as measure_indel_size, but returns the actual
    observed sequence at the locus (not just its length) plus the indel size.

    `read_seq` must already be on the amplicon forward strand (use oriented_seq).
    """
    expected_gap = target_end - target_start
    for L in anchor_steps:
        if L > max_extra:
            break
        la_start = target_start - L
        ra_end = target_end + L
        if la_start < 0 or ra_end > len(amp_seq):
            break
        left_anchor = amp_seq[la_start:target_start]
        right_anchor = amp_seq[target_end:ra_end]
        thresh = max(3, int(mismatch_fraction * L))
        lpos, lmm = find_best_match(left_anchor, read_seq)
        rpos, rmm = find_best_match(right_anchor, read_seq)
        if lpos is None or rpos is None:
            continue
        if lmm <= thresh and rmm <= thresh and rpos >= lpos + len(left_anchor) - 5:
            allele_seq = read_seq[lpos + len(left_anchor) : rpos]
            return len(allele_seq) - expected_gap, allele_seq
    return None, None


def format_allele_display(allele_seq: str, wt_seq: str) -> str:
    """Encode allele relative to WT target for display (amplicon 5'→3').

    - Matching / substituted bases: allele base
    - Deletions (present in WT, absent in allele): ``N``
    - Insertions (extra in allele): inserted bases as written

    Both inputs must be on the same strand (amplicon forward).
    """
    if not wt_seq:
        return allele_seq
    if not allele_seq:
        return "N" * len(wt_seq)

    n, m = len(allele_seq), len(wt_seq)
    # DP[i][j] = best score aligning allele[:i] to wt[:j]
    neg = -10**9
    dp = [[neg] * (m + 1) for _ in range(n + 1)]
    bt = [[0] * (m + 1) for _ in range(n + 1)]  # 0 diag, 1 up (del), 2 left (ins)
    dp[0][0] = 0
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + _ALIGN_GAP
        bt[i][0] = 2
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + _ALIGN_GAP
        bt[0][j] = 1

    for i in range(1, n + 1):
        a = allele_seq[i - 1]
        row = dp[i]
        prev = dp[i - 1]
        for j in range(1, m + 1):
            w = wt_seq[j - 1]
            diag = prev[j - 1] + (_ALIGN_MATCH if a == w else _ALIGN_MISMATCH)
            up = row[j - 1] + _ALIGN_GAP  # gap in allele → deletion vs WT
            left = prev[j] + _ALIGN_GAP  # gap in WT → insertion
            if diag >= up and diag >= left:
                row[j] = diag
                bt[i][j] = 0
            elif up >= left:
                row[j] = up
                bt[i][j] = 1
            else:
                row[j] = left
                bt[i][j] = 2

    out: list[str] = []
    i, j = n, m
    while i > 0 or j > 0:
        move = bt[i][j]
        if i > 0 and j > 0 and move == 0:
            out.append(allele_seq[i - 1])
            i -= 1
            j -= 1
        elif j > 0 and (i == 0 or move == 1):
            out.append("N")
            j -= 1
        else:
            out.append(allele_seq[i - 1])
            i -= 1
    out.reverse()
    return "".join(out)


def measure_indel_size(
    read_seq: str,
    amp_seq: str,
    target_start: int,
    target_end: int,
    mismatch_fraction: float = MISMATCH_FRACTION,
    max_extra: int = MAX_EXTRA,
    anchor_steps=ANCHOR_STEPS,
):
    """Returns net indel size (0 = WT length, + = insertion, - = deletion) for the
    single-guide target window [target_start, target_end) in `amp_seq`, or None if
    it can't be confidently measured (e.g. deletion larger than MAX_EXTRA)."""
    size, _ = extract_allele(
        read_seq,
        amp_seq,
        target_start,
        target_end,
        mismatch_fraction=mismatch_fraction,
        max_extra=max_extra,
        anchor_steps=anchor_steps,
    )
    return size


@dataclass
class IndelCall:
    read_id: str
    sample: str
    guide: str
    indel_size_bp: int
    call: str  # 'WT' | 'in_frame' | 'frameshift'


def classify_frame(indel_size: int) -> str:
    if indel_size == 0:
        return "WT"
    return "in_frame" if indel_size % 3 == 0 else "frameshift"


def export_indel_histogram(indel_sizes: list[int], path: str) -> None:
    """Bar chart of net indel sizes across the batch. Excludes WT (size 0).
    Caller must already filter concatemer artifacts.
    """
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    from collections import Counter
    from matplotlib.patches import Patch

    sizes = [s for s in indel_sizes if s != 0]
    fig, ax = plt.subplots(figsize=(10, 5))
    if not sizes:
        ax.text(
            0.5,
            0.5,
            "No edited reads with a size call",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        ax.set_axis_off()
    else:
        counts = Counter(sizes)
        xs = list(range(min(counts), max(counts) + 1))
        ys = [counts.get(x, 0) for x in xs]
        in_frame_color = "#2A9D8F"
        frameshift_color = "#E76F51"
        colors = [in_frame_color if x % 3 == 0 else frameshift_color for x in xs]
        ax.bar(xs, ys, color=colors, width=0.85, align="center", edgecolor="none")
        ax.legend(
            handles=[
                Patch(facecolor=in_frame_color, label="In-frame (3n bp)"),
                Patch(facecolor=frameshift_color, label="Frameshift"),
            ]
        )
        ax.set_xlabel("Net indel size (bp)")
        ax.set_ylabel("Read count")
        ax.set_title("Indel size distribution (all samples)")
        ax.axvline(0, color="#888888", lw=0.8, ls="--")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
