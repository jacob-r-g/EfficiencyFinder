import tempfile
import unittest
from pathlib import Path

from core.classify import ClassifiedRead
from core.editing import (
    STATUS_DEL_SMALL,
    STATUS_INCONCLUSIVE,
    STATUS_INSERTION,
    STATUS_NOT_SEQUENCED,
    STATUS_SUBSTITUTION,
    STATUS_WT,
    call_editing_status,
    summarize_efficiency,
)
from core.parsing import load_reference_set
from tests.helpers import (
    AMP1,
    AMP1_NAME,
    AMP2_EXCISION,
    AMP2_NAME,
    CAS12_AMP1,
    CAS12_AMP1_NAME,
    CAS12_GUIDE1_NAME,
    CAS12_GUIDE1_START,
    GUIDE1,
    GUIDE1_END,
    GUIDE1_NAME,
    GUIDE1_START,
    GUIDE2A_NAME,
    GUIDE2B_NAME,
    LEFT,
    valid_cas12_single_guide_fasta,
    valid_single_guide_fasta,
    valid_two_guide_fasta,
)

# SpCas9 cut is 3 bp upstream of PAM → index start+17 for a 23 bp NGG guide.
GUIDE1_CUT = GUIDE1_START + 17


def _wt_read(read_id="wt"):
    return ClassifiedRead(read_id, AMP1, AMP1_NAME, "+", 100, 0)


class TestCallEditingStatus(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        fa = valid_single_guide_fasta(Path(self._td.name) / "ref.fa")
        self.ref = load_reference_set(str(fa), flank=25)

    def tearDown(self):
        self._td.cleanup()

    def _call(self, reads):
        return call_editing_status(
            reads,
            self.ref.amplicons,
            self.ref.guides,
            self.ref.guides_by_amplicon,
        )

    def test_wt_intact(self):
        calls = self._call([_wt_read()])
        self.assertEqual(calls[0].status, STATUS_WT)
        self.assertEqual(calls[0].guide, GUIDE1_NAME)

    def test_distal_spacer_indel_still_wt(self):
        """±1 far from the cut (still in spacer) must not count as edited."""
        # Delete 1 bp near the 5' end of the spacer; cut window stays intact.
        read = AMP1[: GUIDE1_START + 2] + AMP1[GUIDE1_START + 3 :]
        cr = ClassifiedRead("distal", read, AMP1_NAME, "+", 100, 0)
        self.assertEqual(self._call([cr])[0].status, STATUS_WT)

    def test_small_deletion_at_cut(self):
        read = AMP1[: GUIDE1_CUT - 2] + AMP1[GUIDE1_CUT + 3 :]  # 5 bp across cut
        cr = ClassifiedRead("d", read, AMP1_NAME, "+", 100, 0)
        self.assertEqual(self._call([cr])[0].status, STATUS_DEL_SMALL)

    def test_insertion_at_cut(self):
        read = AMP1[:GUIDE1_CUT] + "AAAAA" + AMP1[GUIDE1_CUT:]
        cr = ClassifiedRead("i", read, AMP1_NAME, "+", 100, 0)
        self.assertEqual(self._call([cr])[0].status, STATUS_INSERTION)

    def test_substitution_in_cut_window(self):
        chars = list(AMP1)
        for i in range(GUIDE1_CUT - 3, GUIDE1_CUT + 3):
            chars[i] = "A" if AMP1[i] != "A" else "C"
        read = "".join(chars)
        cr = ClassifiedRead("s", read, AMP1_NAME, "+", 100, 0)
        self.assertEqual(self._call([cr])[0].status, STATUS_SUBSTITUTION)

    def test_missing_flanks_inconclusive(self):
        read = AMP1[: GUIDE1_START - 10] + AMP1[GUIDE1_END + 10 :]
        cr = ClassifiedRead("L", read, AMP1_NAME, "+", 100, 0)
        self.assertEqual(self._call([cr])[0].status, STATUS_INCONCLUSIVE)

    def test_not_sequenced_without_coverage(self):
        short = AMP1[:80]
        cr = ClassifiedRead("n", short, AMP1_NAME, "+", 20, 0)
        self.assertEqual(self._call([cr])[0].status, STATUS_NOT_SEQUENCED)

    def test_short_read_covering_only_first_of_two_guides(self):
        """Per-guide coverage: call guide A, leave guide B not_sequenced."""
        with tempfile.TemporaryDirectory() as td:
            fa = valid_two_guide_fasta(Path(td) / "ref.fa")
            ref = load_reference_set(str(fa), flank=25)
        # Covers LEFT + GUIDE1 only — enough for guide A locus, not guide B.
        # Right flank of A is missing → inconclusive at A.
        read = LEFT + GUIDE1
        cr = ClassifiedRead("short", read, AMP2_NAME, "+", 100, 0)
        calls = call_editing_status(
            [cr], ref.amplicons, ref.guides, ref.guides_by_amplicon
        )
        by_guide = {c.guide: c.status for c in calls}
        self.assertEqual(by_guide[GUIDE2A_NAME], STATUS_INCONCLUSIVE)
        self.assertEqual(by_guide[GUIDE2B_NAME], STATUS_NOT_SEQUENCED)

    def test_short_read_can_still_call_wt_on_single_guide(self):
        """A truncated amplicon that still covers one guide's flanks is callable."""
        read = AMP1[GUIDE1_START - 40 : GUIDE1_END + 40]
        cr = ClassifiedRead("span", read, AMP1_NAME, "+", 100, 0)
        self.assertEqual(self._call([cr])[0].status, STATUS_WT)

    def test_paired_excision_read_inconclusive_both_guides(self):
        """Inter-guide dropout: both guides inconclusive (not discarded as not_sequenced)."""
        with tempfile.TemporaryDirectory() as td:
            fa = valid_two_guide_fasta(Path(td) / "ref.fa")
            ref = load_reference_set(str(fa), flank=25)
        cr = ClassifiedRead("ex", AMP2_EXCISION, AMP2_NAME, "+", 100, 0)
        calls = call_editing_status(
            [cr], ref.amplicons, ref.guides, ref.guides_by_amplicon
        )
        by_guide = {c.guide: c.status for c in calls}
        self.assertEqual(by_guide[GUIDE2A_NAME], STATUS_INCONCLUSIVE)
        self.assertEqual(by_guide[GUIDE2B_NAME], STATUS_INCONCLUSIVE)

    def test_unassigned_read_skipped(self):
        cr = ClassifiedRead("u", AMP1, None, "+", 0, 0)
        self.assertEqual(self._call([cr]), [])

    def test_summarize_efficiency(self):
        reads = [
            _wt_read("w1"),
            _wt_read("w2"),
            ClassifiedRead(
                "d",
                AMP1[: GUIDE1_CUT - 2] + AMP1[GUIDE1_CUT + 3 :],
                AMP1_NAME,
                "+",
                100,
                0,
            ),
        ]
        calls = self._call(reads)
        rows = summarize_efficiency(
            calls, self.ref.guides, {AMP1_NAME: 3}, sample="plantA"
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.sample, "plantA")
        self.assertEqual(row.wt_unedited, 2)
        self.assertEqual(row.edited, 1)
        self.assertEqual(row.edited_deletion_small, 1)
        self.assertEqual(row.inconclusive, 0)
        self.assertEqual(row.pct_editing, 33.3)

    def test_inconclusive_excluded_from_pct(self):
        reads = [
            _wt_read("w1"),
            ClassifiedRead(
                "L",
                AMP1[: GUIDE1_START - 10] + AMP1[GUIDE1_END + 10 :],
                AMP1_NAME,
                "+",
                100,
                0,
            ),
        ]
        calls = self._call(reads)
        row = summarize_efficiency(
            calls, self.ref.guides, {AMP1_NAME: 2}, sample="x"
        )[0]
        self.assertEqual(row.wt_unedited, 1)
        self.assertEqual(row.inconclusive, 1)
        self.assertEqual(row.edited, 0)
        self.assertEqual(row.reads_spanning_target, 1)
        self.assertEqual(row.pct_editing, 0.0)


class TestCas12Editing(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        fa = valid_cas12_single_guide_fasta(Path(self._td.name) / "ref.fa")
        self.ref = load_reference_set(str(fa), flank=25, nuclease="cas12")
        self.gi = self.ref.guides[CAS12_GUIDE1_NAME]
        # spacer 16–23 window
        self.wt0 = self.gi.wt_start
        self.wt1 = self.gi.wt_end

    def tearDown(self):
        self._td.cleanup()

    def _call(self, reads):
        return call_editing_status(
            reads,
            self.ref.amplicons,
            self.ref.guides,
            self.ref.guides_by_amplicon,
        )

    def test_wt_intact(self):
        cr = ClassifiedRead("wt", CAS12_AMP1, CAS12_AMP1_NAME, "+", 100, 0)
        self.assertEqual(self._call([cr])[0].status, STATUS_WT)

    def test_distal_spacer_indel_still_wt(self):
        # Delete 1 bp early in spacer (pos 1–2 after PAM); WT window 16–23 intact.
        pam_end = CAS12_GUIDE1_START + 4
        read = CAS12_AMP1[: pam_end + 1] + CAS12_AMP1[pam_end + 2 :]
        cr = ClassifiedRead("distal", read, CAS12_AMP1_NAME, "+", 100, 0)
        self.assertEqual(self._call([cr])[0].status, STATUS_WT)

    def test_indel_in_spacer_16_23_is_edited(self):
        read = CAS12_AMP1[: self.wt0 + 2] + CAS12_AMP1[self.wt0 + 5 :]
        cr = ClassifiedRead("edit", read, CAS12_AMP1_NAME, "+", 100, 0)
        self.assertEqual(self._call([cr])[0].status, STATUS_DEL_SMALL)


if __name__ == "__main__":
    unittest.main()
