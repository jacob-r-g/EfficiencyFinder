"""Shared fuzzy sequence matching. Vectorized ungapped (Hamming) sliding-window
search — deliberately NOT a full aligner.
"""

import numpy as np


def seq_to_arr(s: str) -> np.ndarray:
    return np.frombuffer(s.encode(), dtype=np.uint8)


def find_best_match(
    query: str, target: str, search_start: int = 0, search_end: int | None = None
):
    """Slide `query` across target[search_start:search_end]; return
    (best_position, mismatch_count), or (None, None) if it doesn't fit."""
    qlen, tlen = len(query), len(target)
    if search_end is None:
        search_end = tlen
    search_end = min(search_end, tlen - qlen + 1)
    if search_start >= search_end or qlen == 0:
        return None, None
    q = seq_to_arr(query)
    t = seq_to_arr(target)
    windows = np.lib.stride_tricks.sliding_window_view(
        t[search_start : search_end + qlen - 1], qlen
    )
    mism = (windows != q).sum(axis=1)
    idx = int(np.argmin(mism))
    return search_start + idx, int(mism[idx])


def edit_distance(a: str, b: str, cap: int = 6) -> int:
    """Bounded Levenshtein distance (used only by allele clustering)."""
    la, lb = len(a), len(b)
    if abs(la - lb) > cap:
        return cap + 1
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]


def kmers_in_ref_range(seq: str, start: int, end: int, k: int = 15) -> set[str]:
    """K-mers of `seq` whose start position falls within [start, end). Used for
    presence-based coverage checks — robust to large deletions between the two
    checked windows, unlike naive linear read-span extrapolation.
    """
    start = max(0, start)
    end = min(len(seq), end)
    return set(seq[i : i + k] for i in range(start, max(start, end - k + 1)))
