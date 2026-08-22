import gzip
import tempfile
import unittest
from pathlib import Path

from core.parsing import parse_fastq
from tests.helpers import write_fastq
from web.backend.combine import combine_fastq_files


class TestCombineFastq(unittest.TestCase):
    def test_combine_two_plain_files(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            a = write_fastq(td / "a.fq", [("r1", "AAAA")])
            b = write_fastq(td / "b.fq", [("r2", "CCCC")])
            dest = td / "combined.fastq"
            combine_fastq_files([a, b], dest)
            self.assertEqual(
                parse_fastq(str(dest)),
                [("r1", "AAAA"), ("r2", "CCCC")],
            )

    def test_combine_includes_gzipped(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            a = write_fastq(td / "a.fq", [("r1", "AAAA")])
            raw = write_fastq(td / "b.fq", [("r2", "GGGG")])
            gz = td / "b.fq.gz"
            gz.write_bytes(gzip.compress(raw.read_bytes()))
            dest = td / "combined.fastq"
            combine_fastq_files([a, gz], dest)
            self.assertEqual(
                parse_fastq(str(dest)),
                [("r1", "AAAA"), ("r2", "GGGG")],
            )

    def test_single_file_is_copied(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            a = write_fastq(td / "a.fq", [("r1", "TTTT")])
            dest = td / "combined.fastq"
            combine_fastq_files([a], dest)
            self.assertEqual(parse_fastq(str(dest)), [("r1", "TTTT")])
