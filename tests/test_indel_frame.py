import tempfile
import unittest
from pathlib import Path

from core.indel_frame import classify_frame, extract_allele, measure_indel_size
from core.parsing import load_reference_set
from tests.helpers import (
    AMP1,
    GUIDE1_END,
    GUIDE1_START,
    valid_single_guide_fasta,
)


class TestClassifyFrame(unittest.TestCase):
    def test_wt_and_frame(self):
        self.assertEqual(classify_frame(0), "WT")
        self.assertEqual(classify_frame(3), "in_frame")
        self.assertEqual(classify_frame(-6), "in_frame")
        self.assertEqual(classify_frame(1), "frameshift")
        self.assertEqual(classify_frame(-1), "frameshift")
        self.assertEqual(classify_frame(4), "frameshift")


class TestMeasureIndelSize(unittest.TestCase):
    def test_wt_is_zero(self):
        self.assertEqual(measure_indel_size(AMP1, AMP1, GUIDE1_START, GUIDE1_END), 0)

    def test_exact_deletion(self):
        read = AMP1[: GUIDE1_START + 4] + AMP1[GUIDE1_START + 9 :]  # −5 bp
        self.assertEqual(measure_indel_size(read, AMP1, GUIDE1_START, GUIDE1_END), -5)

    def test_exact_insertion(self):
        read = AMP1[:GUIDE1_START] + "AAA" + AMP1[GUIDE1_START:]
        self.assertEqual(measure_indel_size(read, AMP1, GUIDE1_START, GUIDE1_END), 3)

    def test_substitution_is_size_zero(self):
        """Indel/frame treats substitution-only changes as WT (size 0)."""
        chars = list(AMP1)
        chars[GUIDE1_START] = "A" if AMP1[GUIDE1_START] != "A" else "C"
        read = "".join(chars)
        self.assertEqual(measure_indel_size(read, AMP1, GUIDE1_START, GUIDE1_END), 0)

    def test_anchor_extends_when_near_flank_is_eroded(self):
        # Destroy the inner 8 bp of the left 25 bp flank so the tight anchor
        # cannot match, and delete 12 bp of the target. The 50 bp step should
        # still match and recover the true net indel size.
        flip = {"A": "C", "C": "G", "G": "T", "T": "A"}
        chars = list(AMP1)
        for i in range(GUIDE1_START - 8, GUIDE1_START):
            chars[i] = flip[AMP1[i]]
        read = "".join(chars[:GUIDE1_START] + chars[GUIDE1_START + 12 :])
        self.assertIsNone(
            measure_indel_size(
                read, AMP1, GUIDE1_START, GUIDE1_END, anchor_steps=(25,)
            )
        )
        size = measure_indel_size(read, AMP1, GUIDE1_START, GUIDE1_END)
        self.assertEqual(size, -12)

    def test_extract_allele_returns_observed_sequence(self):
        ins = "GGGAAATTT"
        read = AMP1[:GUIDE1_START] + ins + AMP1[GUIDE1_END:]
        size, seq = extract_allele(read, AMP1, GUIDE1_START, GUIDE1_END)
        self.assertEqual(size, len(ins) - (GUIDE1_END - GUIDE1_START))
        self.assertEqual(seq, ins)

    def test_works_after_loading_reference(self):
        with tempfile.TemporaryDirectory() as td:
            fa = valid_single_guide_fasta(Path(td) / "ref.fa")
            ref = load_reference_set(str(fa))
            gi = next(iter(ref.guides.values()))
            read = AMP1[: gi.target_end - 1] + AMP1[gi.target_end :]
            self.assertEqual(
                measure_indel_size(read, AMP1, gi.target_start, gi.target_end), -1
            )


if __name__ == "__main__":
    unittest.main()
