import tempfile
import unittest
from pathlib import Path

from core.indel_frame import export_indel_histogram
from core.parsing import load_reference_set, revcomp
from core.pipeline import run_batch, run_single_sample
from core.settings import PipelineSettings
from tests.helpers import (
    AMP1,
    AMP1_NAME,
    AMP2,
    AMP2_NAME,
    GUIDE1_END,
    GUIDE1_NAME,
    GUIDE1_START,
    GUIDE2A_NAME,
    GUIDE2B_NAME,
    random_dna,
    valid_single_guide_fasta,
    valid_two_guide_fasta,
    write_fastq,
)


class TestPipeline(unittest.TestCase):
    def test_single_sample_wt_and_deletion(self):
        cut = GUIDE1_START + 17
        deleted = AMP1[: cut - 2] + AMP1[cut + 3 :]  # −5 across cut
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fa = valid_single_guide_fasta(td / "ref.fa")
            fq = write_fastq(
                td / "plantA.fastq",
                [("wt1", AMP1), ("wt2", AMP1), ("del1", deleted), ("del2", deleted)],
            )
            ref = load_reference_set(str(fa))
            result = run_single_sample(str(fq), ref, PipelineSettings())
            self.assertEqual(result.sample_name, "plantA")
            self.assertEqual(result.n_reads, 4)
            self.assertEqual(result.n_assigned, 4)
            self.assertEqual(result.amp_read_counts[AMP1_NAME], 4)

            eff = result.efficiencies[0]
            self.assertEqual(eff.guide, GUIDE1_NAME)
            self.assertEqual(eff.wt_unedited, 2)
            self.assertEqual(eff.edited_deletion_small, 2)
            self.assertEqual(eff.pct_editing, 50.0)

            indel = result.indel_summaries[0]
            self.assertEqual(indel.wt, 2)
            self.assertEqual(indel.edited, 2)
            self.assertEqual(indel.deletions, 2)
            self.assertEqual(indel.frameshift, 2)  # −5 is frameshift
            self.assertEqual(indel.pct_editing, 50.0)

            self.assertGreaterEqual(result.allele_summaries[0].edited_reads, 2)

    def test_batch_progress_and_shared_alleles(self):
        deleted = AMP1[: GUIDE1_START] + AMP1[GUIDE1_START + 1 :]  # −1
        progress = []
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fa = valid_single_guide_fasta(td / "ref.fa")
            fq1 = write_fastq(
                td / "s1.fastq",
                [("wt", AMP1)] * 5 + [("d", deleted)] * 4,
            )
            fq2 = write_fastq(
                td / "s2.fastq",
                [("wt", AMP1)] * 5 + [("d", deleted)] * 4,
            )
            ref = load_reference_set(str(fa))
            batch = run_batch(
                [str(fq1), str(fq2)],
                ref,
                PipelineSettings(min_allele_reads=3),
                progress_callback=lambda i, n, name, **kw: progress.append(
                    (i, n, name, kw.get("stage"), kw.get("stage_i"))
                ),
            )
            samples_seen = {(i, n, name) for i, n, name, *_ in progress}
            self.assertEqual(samples_seen, {(1, 2, "s1"), (2, 2, "s2")})
            stages_s1 = [stage for i, _n, name, stage, _si in progress if name == "s1"]
            self.assertEqual(
                stages_s1,
                [
                    "Reading FASTQ",
                    "Classifying reads",
                    "Calling editing",
                    "Measuring indels & alleles",
                    "Calling paired excision",
                ],
            )
            self.assertEqual(len(batch.samples), 2)
            self.assertEqual(len(batch.efficiencies), 2)
            self.assertTrue(any(s.n_samples == 2 for s in batch.shared_alleles))
            self.assertEqual(batch.n_reads, 18)

    def test_rc_reads_classify_and_score(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fa = valid_single_guide_fasta(td / "ref.fa")
            fq = write_fastq(td / "rc.fastq", [("r", revcomp(AMP1))])
            ref = load_reference_set(str(fa))
            result = run_single_sample(str(fq), ref)
            self.assertEqual(result.n_assigned, 1)
            self.assertEqual(result.efficiencies[0].wt_unedited, 1)

    def test_substitution_counts_as_edited_for_efficiency_but_wt_for_frame(self):
        cut = GUIDE1_START + 17
        chars = list(AMP1)
        for i in range(cut - 3, cut + 3):
            chars[i] = "A" if AMP1[i] != "A" else "C"
        sub = "".join(chars)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fa = valid_single_guide_fasta(td / "ref.fa")
            fq = write_fastq(td / "sub.fastq", [("s", sub)])
            ref = load_reference_set(str(fa))
            result = run_single_sample(str(fq), ref)
            self.assertEqual(result.efficiencies[0].edited_substitution, 1)
            self.assertEqual(result.efficiencies[0].edited, 1)
            self.assertEqual(result.indel_summaries[0].wt, 1)
            self.assertEqual(result.indel_summaries[0].edited, 0)

    def test_artifact_indel_filtered(self):
        # Insertion larger than artifact_size_threshold (concatemer-scale).
        huge = AMP1[:GUIDE1_START] + random_dna(200, seed=7) + AMP1[GUIDE1_END:]
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fa = valid_single_guide_fasta(td / "ref.fa")
            fq = write_fastq(td / "art.fastq", [("a", huge), ("wt", AMP1)])
            ref = load_reference_set(str(fa))
            result = run_single_sample(
                str(fq), ref, PipelineSettings(artifact_size_threshold=100)
            )
            # WT is kept; the concatemer should not appear as an edited count.
            self.assertEqual(result.indel_summaries[0].wt, 1)
            self.assertEqual(result.indel_summaries[0].edited, 0)

    def test_two_guide_amplicon_scores_each_guide(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fa = valid_two_guide_fasta(td / "ref.fa")
            fq = write_fastq(td / "pair.fastq", [("wt", AMP2)] * 3)
            ref = load_reference_set(str(fa))
            result = run_single_sample(str(fq), ref)
            self.assertEqual(result.amp_read_counts[AMP2_NAME], 3)
            by_guide = {e.guide: e for e in result.efficiencies}
            self.assertEqual(set(by_guide), {GUIDE2A_NAME, GUIDE2B_NAME})
            self.assertEqual(by_guide[GUIDE2A_NAME].wt_unedited, 3)
            self.assertEqual(by_guide[GUIDE2B_NAME].wt_unedited, 3)
            self.assertEqual(len(result.indel_summaries), 2)
            self.assertEqual(result.excision_summaries[0].n_simultaneous_large_del, 0)

    def test_unassigned_reads_reported(self):
        junk = random_dna(len(AMP1), seed=42)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fa = valid_single_guide_fasta(td / "ref.fa")
            fq = write_fastq(
                td / "mix.fastq",
                [("wt", AMP1), ("wt2", AMP1), ("junk", junk)],
            )
            ref = load_reference_set(str(fa))
            batch = run_batch([str(fq)], ref)
            self.assertEqual(batch.samples[0].n_reads, 3)
            self.assertEqual(batch.samples[0].n_assigned, 2)
            self.assertEqual(batch.samples[0].n_unassigned, 1)
            self.assertEqual(len(batch.samples[0].unassigned_reads), 1)
            self.assertEqual(batch.samples[0].unassigned_reads[0][0], "junk")
            self.assertEqual(len(batch.amplicon_assignments), 1)
            row = batch.amplicon_assignments[0]
            self.assertEqual(row.amplicon, AMP1_NAME)
            self.assertEqual(row.n_reads, 2)
            self.assertEqual(row.pct_of_sample, 66.7)

    def test_histogram_export(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "h.png"
            export_indel_histogram([-1, -1, 1, 3, 0, 2], str(path))
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
