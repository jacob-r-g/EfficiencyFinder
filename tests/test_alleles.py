import unittest

from core.alleles import call_alleles_for_sample
from core.matching import edit_distance


class TestCallAlleles(unittest.TestCase):
    def test_confident_lowfreq_merge_and_singletons(self):
        allele_a = "A" * 20
        allele_b = "C" * 20
        noisy_a = "A" * 19 + "T"  # distance 1 from A
        self.assertEqual(edit_distance(allele_a, noisy_a, cap=3), 1)
        far = "G" * 20
        singleton = "T" * 20

        reads = (
            [("a", allele_a)] * 10
            + [("b", allele_b)] * 5
            + [("n", noisy_a)] * 2  # should merge into A
            + [("f", far)] * 2  # low-frequency allele
            + [("s", singleton)]  # dropped
        )
        conf, extra, merged, singles = call_alleles_for_sample(
            reads, min_allele_reads=3, merge_edit_dist=2
        )
        self.assertEqual(conf, [(allele_a, 10), (allele_b, 5)])
        self.assertEqual(extra, [(far, 2)])
        self.assertEqual(merged, 2)
        self.assertEqual(singles, 1)

    def test_empty(self):
        conf, extra, merged, singles = call_alleles_for_sample([])
        self.assertEqual(conf, [])
        self.assertEqual(extra, [])
        self.assertEqual(merged, 0)
        self.assertEqual(singles, 0)

    def test_all_below_threshold_recurring_is_low_freq(self):
        seq = "ACGTACGT"
        reads = [("r", seq)] * 2
        conf, extra, merged, singles = call_alleles_for_sample(
            reads, min_allele_reads=3, merge_edit_dist=2
        )
        self.assertEqual(conf, [])
        self.assertEqual(extra, [(seq, 2)])
        self.assertEqual(merged, 0)
        self.assertEqual(singles, 0)


if __name__ == "__main__":
    unittest.main()
