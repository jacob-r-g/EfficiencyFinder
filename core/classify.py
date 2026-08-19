"""Read-to-amplicon classification via shared k-mer counting."""

from dataclasses import dataclass

from .parsing import revcomp

K_CLASSIFY = 17
MIN_CLASSIFY_SCORE = 15  # minimum shared k-mers to confidently assign a read


def kmer_set(seq: str, k: int = K_CLASSIFY) -> set[str]:
    if k <= 0 or len(seq) < k:
        return set()
    return set(seq[i : i + k] for i in range(len(seq) - k + 1))


@dataclass
class ClassifiedRead:
    read_id: str
    seq: str
    amplicon: str | None  # None if unassigned (score below MIN_CLASSIFY_SCORE)
    orientation: str  # '+' or '-'
    score: int
    second_best_score: int

    @property
    def oriented_seq(self) -> str:
        return self.seq if self.orientation == "+" else revcomp(self.seq)


def classify_reads(
    reads,
    amplicons: dict[str, str],
    k: int = K_CLASSIFY,
    min_score: int = MIN_CLASSIFY_SCORE,
) -> list[ClassifiedRead]:
    amp_kmers = {name: kmer_set(seq, k) for name, seq in amplicons.items()}
    results = []
    for read_id, seq in reads:
        fwd_k = kmer_set(seq, k)
        rc_k = kmer_set(revcomp(seq), k)
        scores = []
        for amp, aks in amp_kmers.items():
            f, r = len(fwd_k & aks), len(rc_k & aks)
            scores.append((amp, "+", f) if f >= r else (amp, "-", r))
        scores.sort(key=lambda x: -x[2])
        if not scores:
            results.append(ClassifiedRead(read_id, seq, None, "+", 0, 0))
            continue
        best = scores[0]
        # IMPORTANT: guard len(scores) > 1 -- a FASTA with only ONE amplicon has no
        # "second place" to compare against. This crashed the first version of the
        # pipeline on a single-amplicon input file.
        second = scores[1] if len(scores) > 1 else (None, "+", 0)
        amp_call = best[0] if best[2] >= min_score else None
        results.append(
            ClassifiedRead(read_id, seq, amp_call, best[1], best[2], second[2])
        )
    return results
