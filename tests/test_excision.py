import tempfile
import unittest
from pathlib import Path

from core.classify import ClassifiedRead
from core.editing import (
    STATUS_DEL_SMALL,
    STATUS_INCONCLUSIVE,
    STATUS_WT,
    call_editing_status,
)
from core.excision import call_paired_excisions
from core.parsing import load_reference_set
from core.pipeline import run_single_sample
from core.settings import PipelineSettings
from tests.helpers import (
    AMP2,
    AMP2_EXCISION,
    AMP2_NAME,
    GUIDE1_START,
    GUIDE2A_NAME,
    GUIDE2B_NAME,
    GUIDE2_END,
    GUIDE2_START,
    valid_two_guide_fasta,
    write_fastq,
)


class TestPairedExcision(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        fa = valid_two_guide_fasta(Path(self._td.name) / "ref.fa")
        self.ref = load_reference_set(str(fa), flank=25)
        self.settings = PipelineSettings()

    def tearDown(self):
        self._td.cleanup()

    def test_wt_is_not_excision(self):
        cr = ClassifiedRead("wt", AMP2, AMP2_NAME, "+", 100, 0)
        calls = call_editing_status(
            [cr],
            self.ref.amplicons,
            self.ref.guides,
            self.ref.guides_by_amplicon,
            self.settings,
        )
        summaries, sizes = call_paired_excisions(
            [cr], calls, self.ref.guides, self.ref.guides_by_amplicon, self.settings, "s"
        )
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].n_spanning_reads, 1)
        self.assertEqual(summaries[0].n_simultaneous_large_del, 0)
        self.assertEqual(summaries[0].n_confirmed_excision, 0)
        self.assertEqual(sizes, [])

    def test_intervening_dropout_is_confirmed_excision(self):
        cr = ClassifiedRead("ex", AMP2_EXCISION, AMP2_NAME, "+", 100, 0)
        calls = call_editing_status(
            [cr],
            self.ref.amplicons,
            self.ref.guides,
            self.ref.guides_by_amplicon,
            self.settings,
        )
        by_guide = {c.guide: c.status for c in calls}
        self.assertEqual(by_guide[GUIDE2A_NAME], STATUS_INCONCLUSIVE)
        self.assertEqual(by_guide[GUIDE2B_NAME], STATUS_INCONCLUSIVE)

        summaries, sizes = call_paired_excisions(
            [cr], calls, self.ref.guides, self.ref.guides_by_amplicon, self.settings, "s"
        )
        row = summaries[0]
        # SpCas9 cuts 3 bp upstream of PAM → cut-to-cut expected dropout.
        cut_left = GUIDE1_START + 17
        cut_right = GUIDE2_START + 17
        expected_cuts = cut_right - cut_left
        # AMP2_EXCISION drops both full guides + MID; flank-measured size is larger.
        measured = GUIDE2_END - GUIDE1_START
        self.assertEqual(row.expected_dropout_bp, expected_cuts)
        self.assertEqual(row.n_spanning_reads, 1)
        self.assertEqual(row.n_simultaneous_large_del, 1)
        self.assertEqual(row.n_confirmed_excision, 1)
        self.assertEqual(row.median_excision_bp, float(measured))
        self.assertEqual(sizes[0].excision_size_bp, measured)
        self.assertEqual(sizes[0].n_reads, 1)

    def test_single_guide_small_indel_is_not_paired_excision(self):
        # Independent 5 bp deletion across guide-1 cut; guide 2 remains WT.
        cut = GUIDE1_START + 17
        read = AMP2[: cut - 2] + AMP2[cut + 3 :]
        cr = ClassifiedRead("one", read, AMP2_NAME, "+", 100, 0)
        calls = call_editing_status(
            [cr],
            self.ref.amplicons,
            self.ref.guides,
            self.ref.guides_by_amplicon,
            self.settings,
        )
        by_guide = {c.guide: c.status for c in calls}
        self.assertEqual(by_guide[GUIDE2A_NAME], STATUS_DEL_SMALL)
        self.assertEqual(by_guide[GUIDE2B_NAME], STATUS_WT)
        summaries, _sizes = call_paired_excisions(
            [cr], calls, self.ref.guides, self.ref.guides_by_amplicon, self.settings, "s"
        )
        self.assertEqual(summaries[0].n_simultaneous_large_del, 0)
        self.assertEqual(summaries[0].n_confirmed_excision, 0)

    def test_pipeline_counts_excision_among_mixed_reads(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fa = valid_two_guide_fasta(td / "ref.fa")
            fq = write_fastq(
                td / "mix.fastq",
                [("wt", AMP2)] * 2 + [("ex", AMP2_EXCISION)] * 3,
            )
            ref = load_reference_set(str(fa))
            result = run_single_sample(str(fq), ref)
            self.assertEqual(len(result.excision_summaries), 1)
            row = result.excision_summaries[0]
            self.assertEqual(row.n_spanning_reads, 5)
            self.assertEqual(row.n_simultaneous_large_del, 3)
            self.assertEqual(row.n_confirmed_excision, 3)
            self.assertEqual(row.pct_simultaneous_large_del, 60.0)


if __name__ == "__main__":
    unittest.main()
