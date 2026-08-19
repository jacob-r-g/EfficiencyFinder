"""Allele clustering + nanopore-noise filtering for chimerism detection."""

from collections import Counter

from .matching import edit_distance

MIN_ALLELE_READS = 3
MERGE_EDIT_DIST = 2


def call_alleles_for_sample(
    edited_reads: list[tuple[str, str]],  # [(read_id, allele_seq), ...]
    min_allele_reads=MIN_ALLELE_READS,
    merge_edit_dist=MERGE_EDIT_DIST,
):
    """Returns (confident_alleles, low_freq_alleles, merged_noise_count, singleton_excluded_count)
    where each allele entry is (sequence, read_count)."""
    seq_counts = Counter(seq for _, seq in edited_reads)
    ranked = seq_counts.most_common()
    confident = [(sq, n) for sq, n in ranked if n >= min_allele_reads]
    low_support = [(sq, n) for sq, n in ranked if n < min_allele_reads]

    merged_into = 0
    unmerged_low = []
    for sq, n in low_support:
        best_match, best_dist = None, merge_edit_dist + 1
        for csq, _cn in confident:
            d = edit_distance(sq, csq, cap=merge_edit_dist + 1)
            if d <= merge_edit_dist and d < best_dist:
                best_match, best_dist = csq, d
        if best_match is not None:
            merged_into += n
        else:
            unmerged_low.append((sq, n))

    extra_alleles = [(sq, n) for sq, n in unmerged_low if n >= 2]
    residual_noise_reads = sum(n for sq, n in unmerged_low if n == 1)
    return confident, extra_alleles, merged_into, residual_noise_reads
