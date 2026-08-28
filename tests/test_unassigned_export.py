import tempfile
import unittest
from pathlib import Path

from core.parsing import parse_fastq, write_fastq
from core.pipeline import SampleResult
from web.backend.unassigned_export import safe_sample_slug, write_unassigned_exports


class TestUnassignedExport(unittest.TestCase):
    def test_safe_sample_slug(self):
        self.assertEqual(safe_sample_slug("plant A"), "plant_A")

    def test_write_exports_one_file_per_sample(self):
        with tempfile.TemporaryDirectory() as td:
            export_dir = Path(td) / "exports"
            samples = [
                SampleResult(
                    sample_name="s1",
                    fastq_path="",
                    n_reads=2,
                    n_assigned=1,
                    n_unassigned=1,
                    amp_read_counts={},
                    unassigned_reads=[("r1", "ACGT")],
                    efficiencies=[],
                    indel_summaries=[],
                    allele_summaries=[],
                    allele_details=[],
                    indel_size_obs=[],
                    indel_sizes=[],
                    excision_summaries=[],
                    excision_sizes=[],
                )
            ]
            meta = write_unassigned_exports(samples, export_dir)
            self.assertEqual(len(meta), 1)
            self.assertEqual(meta[0]["n_reads"], 1)
            path = export_dir / meta[0]["filename"]
            self.assertTrue(path.is_file())
            self.assertEqual(parse_fastq(str(path)), [("r1", "ACGT")])

    def test_write_fastq_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "out.fq"
            write_fastq(str(path), [("a", "AAAA"), ("b", "CCCC")])
            self.assertEqual(parse_fastq(str(path)), [("a", "AAAA"), ("b", "CCCC")])


if __name__ == "__main__":
    unittest.main()
