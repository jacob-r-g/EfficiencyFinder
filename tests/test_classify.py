import tempfile
import unittest
from pathlib import Path

from core.classify import classify_reads
from core.parsing import load_reference_set, revcomp
from tests.helpers import (
    AMP1,
    AMP1_NAME,
    AMP2,
    AMP2_NAME,
    random_dna,
    valid_single_guide_fasta,
)


class TestClassifyReads(unittest.TestCase):
    def test_assigns_forward_and_reverse(self):
        reads = [
            ("fwd", AMP1),
            ("rev", revcomp(AMP1)),
        ]
        results = classify_reads(reads, {AMP1_NAME: AMP1})
        by_id = {r.read_id: r for r in results}
        self.assertEqual(by_id["fwd"].amplicon, AMP1_NAME)
        self.assertEqual(by_id["fwd"].orientation, "+")
        self.assertGreaterEqual(by_id["fwd"].score, 15)
        self.assertEqual(by_id["rev"].amplicon, AMP1_NAME)
        self.assertEqual(by_id["rev"].orientation, "-")
        self.assertEqual(by_id["rev"].oriented_seq, AMP1)

    def test_unrelated_sequence_unassigned(self):
        junk = random_dna(len(AMP1), seed=99)
        results = classify_reads([("x", junk)], {AMP1_NAME: AMP1})
        self.assertIsNone(results[0].amplicon)
        self.assertLess(results[0].score, 15)

    def test_single_amplicon_does_not_crash(self):
        """Regression: a FASTA with one amplicon has no second-best score."""
        with tempfile.TemporaryDirectory() as td:
            fa = valid_single_guide_fasta(Path(td) / "ref.fa")
            ref = load_reference_set(str(fa))
            self.assertEqual(len(ref.amplicons), 1)
            results = classify_reads([("r", AMP1)], ref.amplicons)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].amplicon, AMP1_NAME)
            self.assertEqual(results[0].second_best_score, 0)

    def test_chooses_correct_amplicon_among_two(self):
        amplicons = {AMP1_NAME: AMP1, AMP2_NAME: AMP2}
        results = classify_reads([("a", AMP1), ("b", AMP2)], amplicons)
        by_id = {r.read_id: r for r in results}
        self.assertEqual(by_id["a"].amplicon, AMP1_NAME)
        self.assertEqual(by_id["b"].amplicon, AMP2_NAME)
        self.assertGreater(by_id["a"].score, by_id["a"].second_best_score)

    def test_sliced_amplicon_still_assigns(self):
        slice_read = AMP1[20:380]
        results = classify_reads([("s", slice_read)], {AMP1_NAME: AMP1})
        self.assertEqual(results[0].amplicon, AMP1_NAME)
        self.assertEqual(results[0].orientation, "+")


if __name__ == "__main__":
    unittest.main()
