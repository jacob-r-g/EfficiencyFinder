import tempfile
import unittest
from pathlib import Path

from core.indel_frame import (
    classify_frame,
    extract_allele,
    format_allele_display,
    measure_indel_size,
)
from core.parsing import load_reference_set, revcomp
from tests.helpers import (
    AMP1,
    GUIDE1,
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


class TestFormatAlleleDisplay(unittest.TestCase):
    def test_deletion_uses_n(self):
        wt = "ACGTACGT"
        allele = "ACGTGT"  # deleted AC in the middle
        disp = format_allele_display(allele, wt)
        self.assertEqual(disp.count("N"), 2)
        self.assertEqual(len(disp) - disp.count("N"), len(allele))
        self.assertTrue(disp.startswith("ACGT"))
        self.assertTrue(disp.endswith("GT"))

    def test_insertion_keeps_extra_bases(self):
        wt = "ACGT"
        allele = "ACGGGT"
        disp = format_allele_display(allele, wt)
        self.assertNotIn("N", disp)
        self.assertIn("GGG", disp)
        self.assertEqual(len(disp), len(allele))

    def test_substitution_shows_allele_base(self):
        wt = "ACGT"
        allele = "ACCT"
        self.assertEqual(format_allele_display(allele, wt), "ACCT")

    def test_identical_is_unchanged(self):
        wt = GUIDE1
        self.assertEqual(format_allele_display(wt, wt), wt)

    def test_rc_read_allele_matches_forward_display(self):
        """Alleles extracted from RC-oriented reads stay amplicon 5'→3'."""
        # 5 bp deletion inside the guide on the forward amplicon.
        fwd_read = AMP1[: GUIDE1_START + 4] + AMP1[GUIDE1_START + 9 :]
        size_f, seq_f = extract_allele(fwd_read, AMP1, GUIDE1_START, GUIDE1_END)
        # Same molecule sequenced opposite strand: classify stores RC as seq and
        # orientation '-', then oriented_seq = revcomp(seq) recovers forward.
        raw_rc = revcomp(fwd_read)
        oriented = revcomp(raw_rc)
        size_r, seq_r = extract_allele(oriented, AMP1, GUIDE1_START, GUIDE1_END)
        self.assertEqual(oriented, fwd_read)
        self.assertEqual(size_f, size_r)
        self.assertEqual(seq_f, seq_r)
        wt = AMP1[GUIDE1_START:GUIDE1_END]
        self.assertEqual(
            format_allele_display(seq_f, wt), format_allele_display(seq_r, wt)
        )
        self.assertIn("N", format_allele_display(seq_f, wt))


if __name__ == "__main__":
    unittest.main()
