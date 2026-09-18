"""Unit tests for nuclease geometry (Cas9 / Cas12 WT windows)."""

import unittest

from core.nuclease import guide_geometry, normalize_nuclease


class TestNormalizeNuclease(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(normalize_nuclease(None), "cas9")
        self.assertEqual(normalize_nuclease("Cas9"), "cas9")
        self.assertEqual(normalize_nuclease("spCas9"), "cas9")
        self.assertEqual(normalize_nuclease("Cas12a"), "cas12")
        self.assertEqual(normalize_nuclease("Cpf1"), "cas12")

    def test_unknown(self):
        with self.assertRaises(ValueError):
            normalize_nuclease("cas13")


class TestGuideGeometryCas9(unittest.TestCase):
    def test_plus_strand(self):
        # 23 bp guide: cut between spacer 17–18 → index pos+17; WT = cut±3.
        cut, wt0, wt1 = guide_geometry(nuclease="cas9", pos=100, guide_len=23, strand="+")
        self.assertEqual(cut, 117)
        self.assertEqual((wt0, wt1), (114, 120))

    def test_minus_strand(self):
        cut, wt0, wt1 = guide_geometry(nuclease="cas9", pos=100, guide_len=23, strand="-")
        self.assertEqual(cut, 106)
        self.assertEqual((wt0, wt1), (103, 109))


class TestGuideGeometryCas12(unittest.TestCase):
    def test_plus_strand_spacer_16_23(self):
        # PAM 4 bp + 23 spacer; WT = spacer 16–23 → [pos+19, pos+27).
        cut, wt0, wt1 = guide_geometry(
            nuclease="cas12", pos=100, guide_len=27, strand="+"
        )
        self.assertEqual(cut, 121)  # PAM + spacer pos 17
        self.assertEqual((wt0, wt1), (119, 127))
        self.assertEqual(wt1 - wt0, 8)

    def test_minus_strand(self):
        cut, wt0, wt1 = guide_geometry(
            nuclease="cas12", pos=100, guide_len=27, strand="-"
        )
        self.assertEqual(cut, 100 + 23 - 17)  # 106
        self.assertEqual((wt0, wt1), (100, 108))


if __name__ == "__main__":
    unittest.main()
