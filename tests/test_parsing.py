import gzip
import tempfile
import unittest
from pathlib import Path

from core.parsing import (
    FastaValidationError,
    load_reference_set,
    parse_fasta,
    parse_fastq,
    revcomp,
    sample_name_from_path,
)
from tests.helpers import (
    AMP1,
    AMP1_NAME,
    AMP2,
    AMP2_NAME,
    CAS12_GUIDE1_NAME,
    CAS12_GUIDE1_START,
    GUIDE1,
    GUIDE1_END,
    GUIDE1_NAME,
    GUIDE1_START,
    GUIDE2,
    GUIDE2A_NAME,
    GUIDE2B_NAME,
    valid_cas12_single_guide_fasta,
    valid_single_guide_fasta,
    valid_two_guide_fasta,
    write_fasta,
    write_fastq,
)


class TestRevcomp(unittest.TestCase):
    def test_revcomp(self):
        self.assertEqual(revcomp("ATGC"), "GCAT")
        self.assertEqual(revcomp(GUIDE1), revcomp(GUIDE1))
        self.assertEqual(revcomp(revcomp(GUIDE1)), GUIDE1)


class TestParseFastaFastq(unittest.TestCase):
    def test_parse_fasta_and_fastq(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fa = write_fasta(td / "a.fa", {"X": "acgt", "Y": "tttt"})
            entries = parse_fasta(str(fa))
            self.assertEqual(entries["X"], "ACGT")
            self.assertEqual(entries["Y"], "TTTT")
            fq = write_fastq(td / "a.fq", [("r1", "acgtacgt")])
            reads = parse_fastq(str(fq))
            self.assertEqual(reads, [("r1", "ACGTACGT")])

    def test_parse_gzipped_fastq(self):
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td) / "a.fastq"
            write_fastq(raw, [("r1", "acgtacgt")])
            gz = Path(td) / "a.fastq.gz"
            gz.write_bytes(gzip.compress(raw.read_bytes()))
            reads = parse_fastq(str(gz))
            self.assertEqual(reads, [("r1", "ACGTACGT")])

    def test_sample_name_strips_fastq_gz(self):
        self.assertEqual(sample_name_from_path("plantA.fastq.gz"), "plantA")
        self.assertEqual(sample_name_from_path("/tmp/plantA.fq"), "plantA")
        self.assertEqual(sample_name_from_path("ref.fa"), "ref")

    def test_empty_fasta_raises(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "empty.fa"
            p.write_text("")
            with self.assertRaises(FastaValidationError) as ctx:
                load_reference_set(str(p))
            self.assertIn("No FASTA records", str(ctx.exception))


class TestLoadReferenceSet(unittest.TestCase):
    def test_valid_single_guide(self):
        with tempfile.TemporaryDirectory() as td:
            fa = valid_single_guide_fasta(Path(td) / "ref.fa")
            ref = load_reference_set(str(fa), flank=25)
            self.assertIn(AMP1_NAME, ref.amplicons)
            self.assertEqual(ref.amplicons[AMP1_NAME], AMP1)
            gi = ref.guides[GUIDE1_NAME]
            self.assertEqual(gi.amplicon, AMP1_NAME)
            self.assertEqual(gi.target, GUIDE1)
            self.assertEqual(gi.target_start, GUIDE1_START)
            self.assertEqual(gi.target_end, GUIDE1_END)
            self.assertEqual(gi.strand, "+")
            self.assertEqual(gi.cut_pos, GUIDE1_START + 17)
            self.assertEqual(gi.wt_start, GUIDE1_START + 14)
            self.assertEqual(gi.wt_end, GUIDE1_START + 20)
            self.assertEqual(gi.left_flank, AMP1[GUIDE1_START - 25 : GUIDE1_START])
            self.assertEqual(gi.right_flank, AMP1[GUIDE1_END : GUIDE1_END + 25])
            self.assertEqual(ref.guides_by_amplicon[AMP1_NAME], [GUIDE1_NAME])
            self.assertEqual(ref.nuclease, "cas9")

    def test_cas12_geometry(self):
        with tempfile.TemporaryDirectory() as td:
            fa = valid_cas12_single_guide_fasta(Path(td) / "ref.fa")
            ref = load_reference_set(str(fa), flank=25, nuclease="cas12")
            gi = ref.guides[CAS12_GUIDE1_NAME]
            self.assertEqual(gi.target_start, CAS12_GUIDE1_START)
            self.assertEqual(gi.cut_pos, CAS12_GUIDE1_START + 4 + 17)
            self.assertEqual(gi.wt_start, CAS12_GUIDE1_START + 4 + 15)
            self.assertEqual(gi.wt_end, CAS12_GUIDE1_START + 4 + 23)
            self.assertEqual(ref.nuclease, "cas12")

    def test_valid_two_guide_amplicon(self):
        with tempfile.TemporaryDirectory() as td:
            fa = valid_two_guide_fasta(Path(td) / "ref.fa")
            ref = load_reference_set(str(fa))
            self.assertEqual(set(ref.guides), {GUIDE2A_NAME, GUIDE2B_NAME})
            self.assertEqual(ref.guides[GUIDE2A_NAME].target, GUIDE1)
            self.assertEqual(ref.guides[GUIDE2B_NAME].target, GUIDE2)
            self.assertEqual(
                set(ref.guides_by_amplicon[AMP2_NAME]), {GUIDE2A_NAME, GUIDE2B_NAME}
            )

    def test_reverse_complement_guide(self):
        with tempfile.TemporaryDirectory() as td:
            fa = write_fasta(
                Path(td) / "rc.fa",
                {AMP1_NAME: AMP1, GUIDE1_NAME: revcomp(GUIDE1)},
            )
            ref = load_reference_set(str(fa))
            gi = ref.guides[GUIDE1_NAME]
            self.assertEqual(gi.target, GUIDE1)
            self.assertEqual(gi.target_start, GUIDE1_START)
            self.assertEqual(gi.target_end, GUIDE1_END)
            self.assertEqual(gi.strand, "-")
            self.assertEqual(gi.cut_pos, GUIDE1_START + 6)
            self.assertEqual(gi.wt_start, GUIDE1_START + 3)
            self.assertEqual(gi.wt_end, GUIDE1_START + 9)

    def test_mismatched_guide_amplicon_name(self):
        with tempfile.TemporaryDirectory() as td:
            fa = write_fasta(
                Path(td) / "bad.fa",
                {AMP1_NAME: AMP1, "Line10_G72": GUIDE1},
            )
            with self.assertRaises(FastaValidationError) as ctx:
                load_reference_set(str(fa))
            msg = str(ctx.exception)
            self.assertIn("Line10_G72", msg)
            self.assertIn("Line10", msg)

    def test_guide_not_found_on_either_strand(self):
        with tempfile.TemporaryDirectory() as td:
            fa = write_fasta(
                Path(td) / "bad.fa",
                {AMP1_NAME: AMP1, GUIDE1_NAME: "AAAAAAAAAAAAAAAAAAAAAAA"},
            )
            with self.assertRaises(FastaValidationError) as ctx:
                load_reference_set(str(fa))
            self.assertIn("was not found", str(ctx.exception))
            self.assertIn(GUIDE1_NAME, str(ctx.exception))

    def test_empty_guide_sequence_silently_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            fa = write_fasta(
                Path(td) / "emptyg.fa",
                {AMP1_NAME: AMP1, GUIDE1_NAME: GUIDE1, "Amp1_Gskip": ""},
            )
            ref = load_reference_set(str(fa))
            self.assertNotIn("Amp1_Gskip", ref.guides)
            self.assertIn(GUIDE1_NAME, ref.guides)

    def test_no_amplicon_entries(self):
        with tempfile.TemporaryDirectory() as td:
            fa = write_fasta(Path(td) / "nog.fa", {"Foo_G1": GUIDE1})
            with self.assertRaises(FastaValidationError) as ctx:
                load_reference_set(str(fa))
            self.assertIn("No amplicon entries", str(ctx.exception))

    def test_zero_guide_amplicon_is_valid(self):
        with tempfile.TemporaryDirectory() as td:
            fa = write_fasta(Path(td) / "noguides.fa", {AMP1_NAME: AMP1})
            ref = load_reference_set(str(fa))
            self.assertEqual(ref.guides, {})
            self.assertEqual(ref.guides_by_amplicon[AMP1_NAME], [])


if __name__ == "__main__":
    unittest.main()
