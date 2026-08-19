import unittest

from core.matching import edit_distance, find_best_match, kmers_in_ref_range


class TestFindBestMatch(unittest.TestCase):
    def test_exact_match(self):
        pos, mm = find_best_match("ACGT", "TTACGTTT")
        self.assertEqual(pos, 2)
        self.assertEqual(mm, 0)

    def test_prefers_lowest_mismatches(self):
        pos, mm = find_best_match("AAAA", "AATAACAAAA")
        self.assertEqual(pos, 6)
        self.assertEqual(mm, 0)

    def test_too_long_returns_none(self):
        pos, mm = find_best_match("ACGTACGT", "ACGT")
        self.assertIsNone(pos)
        self.assertIsNone(mm)

    def test_empty_query(self):
        pos, mm = find_best_match("", "ACGT")
        self.assertIsNone(pos)
        self.assertIsNone(mm)


class TestEditDistance(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(edit_distance("ACGT", "ACGT"), 0)

    def test_one_sub(self):
        self.assertEqual(edit_distance("ACGT", "ACCT", cap=6), 1)

    def test_length_cap(self):
        self.assertEqual(edit_distance("A" * 10, "A", cap=2), 3)


class TestKmersInRefRange(unittest.TestCase):
    def test_range(self):
        seq = "ABCDEFGHIJKLMNO"  # not DNA; function is sequence-agnostic
        kmers = kmers_in_ref_range(seq, 0, 5, k=3)
        self.assertEqual(kmers, {"ABC", "BCD", "CDE"})


if __name__ == "__main__":
    unittest.main()
