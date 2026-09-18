import tempfile
import threading
import time
import unittest
from pathlib import Path

from web.backend.jobs import JobManager
from web.backend.store import Store, StoreError


def _wait(manager: JobManager, job_id: str, status: str, timeout: float = 2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if manager.get(job_id).status == status:
            return
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} never reached {status}")


class TestJobManager(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._td.name))

    def tearDown(self):
        self._td.cleanup()

    def _seed_upload(self, fasta=b">Amp1\nACGT\n", fastq=b"@r1\nACGT\n+\nIIII\n"):
        uid = self.store.new_upload_id()
        self.store.write_chunk(uid, "ref.fa", 0, 1, fasta)
        self.store.write_chunk(uid, "s.fq", 0, 1, fastq)
        return uid

    def test_submit_runs_analyze_and_drops_inputs(self):
        gate = threading.Event()

        def analyze(fasta, fastqs, settings, on_progress, job_dir=None):
            on_progress(1, 1, "s", stage="Classifying reads", stage_i=2, stage_n=5)
            gate.wait(timeout=1)
            return {"ok": True, "fasta": fasta.name}

        manager = JobManager(self.store, analyze=analyze)
        uid = self._seed_upload()
        state = manager.submit(uid, "ref.fa", ["s.fq"], {})
        _wait(manager, state.id, "running")
        self.assertEqual(
            manager.get(state.id).progress,
            {
                "i": 1,
                "n": 1,
                "sample": "s",
                "stage": "Classifying reads",
                "stage_i": 2,
                "stage_n": 5,
            },
        )
        gate.set()
        _wait(manager, state.id, "done")
        done = manager.get(state.id)
        self.assertEqual(done.results, {"ok": True, "fasta": "ref.fa"})
        self.assertFalse((self.store.job_path(state.id) / "inputs").exists())

    def test_second_job_waits_until_first_finishes(self):
        release_first = threading.Event()
        saw_second_while_first_running = threading.Event()

        def analyze(fasta, fastqs, settings, on_progress, job_dir=None):
            if fasta.name == "ref.fa":
                if not release_first.wait(timeout=1):
                    raise AssertionError("first job not released")
            return {"name": fasta.name}

        manager = JobManager(self.store, analyze=analyze)
        first = manager.submit(self._seed_upload(), "ref.fa", ["s.fq"], {})
        _wait(manager, first.id, "running")
        uid2 = self.store.new_upload_id()
        self.store.write_chunk(uid2, "other.fa", 0, 1, b">x\nACGT\n")
        self.store.write_chunk(uid2, "s.fq", 0, 1, b"@r1\nACGT\n+\nIIII\n")
        second = manager.submit(uid2, "other.fa", ["s.fq"], {})
        time.sleep(0.05)
        self.assertEqual(manager.get(second.id).status, "queued")
        saw_second_while_first_running.set()
        release_first.set()
        _wait(manager, first.id, "done")
        _wait(manager, second.id, "done")
        self.assertTrue(saw_second_while_first_running.is_set())

    def test_missing_fasta_rejected(self):
        manager = JobManager(self.store, analyze=lambda *a: {})
        uid = self._seed_upload()
        with self.assertRaises(StoreError):
            manager.submit(uid, "nope.fa", ["s.fq"], {})

    def test_combine_fastqs_passes_single_file(self):
        seen = {}

        def analyze(fasta, fastqs, settings, on_progress, job_dir=None):
            seen["names"] = [p.name for p in fastqs]
            seen["n_reads"] = sum(
                1 for p in fastqs for line in p.read_text().splitlines() if line.startswith("@")
            )
            return {"ok": True}

        manager = JobManager(self.store, analyze=analyze)
        uid = self.store.new_upload_id()
        self.store.write_chunk(uid, "ref.fa", 0, 1, b">Amp1\nACGT\n")
        self.store.write_chunk(uid, "a.fq", 0, 1, b"@r1\nAAAA\n+\nIIII\n")
        self.store.write_chunk(uid, "b.fq", 0, 1, b"@r2\nCCCC\n+\nIIII\n")
        state = manager.submit(
            uid, "ref.fa", ["a.fq", "b.fq"], {}, combine_fastqs=True
        )
        _wait(manager, state.id, "done")
        self.assertEqual(seen["names"], ["combined.fastq"])
        self.assertEqual(seen["n_reads"], 2)
