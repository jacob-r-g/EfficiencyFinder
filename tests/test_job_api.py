import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from core.parsing import parse_fastq
from tests.helpers import AMP1, GUIDE1_NAME, GUIDE1_START, random_dna, valid_single_guide_fasta, write_fastq
from web.backend.app import create_app
from web.backend.store import Store


def _wait_status(client: TestClient, job_id: str, timeout: float = 2.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f"/api/jobs/{job_id}").json()
        if data["status"] in {"done", "failed"}:
            return data
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish")


class TestJobApi(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._td.name))
        self.client = TestClient(
            create_app(self.store, analyze=lambda *a: {"ok": True})
        )

    def tearDown(self):
        self._td.cleanup()

    def _upload(self):
        uid = self.client.post("/api/uploads").json()["upload_id"]
        self.client.put(
            f"/api/uploads/{uid}/files/ref.fa?chunk=0&chunks=1",
            content=b">Amp1\nACGT\n",
        )
        self.client.put(
            f"/api/uploads/{uid}/files/s.fq?chunk=0&chunks=1",
            content=b"@r1\nACGT\n+\nIIII\n",
        )
        return uid

    def test_create_and_fetch_results(self):
        uid = self._upload()
        created = self.client.post(
            "/api/jobs",
            json={"upload_id": uid, "fasta": "ref.fa", "fastqs": ["s.fq"]},
        )
        self.assertEqual(created.status_code, 200)
        job_id = created.json()["id"]
        status = _wait_status(self.client, job_id)
        self.assertEqual(status["status"], "done")
        results = self.client.get(f"/api/jobs/{job_id}/results")
        self.assertEqual(results.json(), {"ok": True})

    def test_unknown_job_is_404(self):
        res = self.client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
        self.assertEqual(res.status_code, 404)


class TestJobPipelineApi(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._td.name))
        self.client = TestClient(create_app(self.store))

    def tearDown(self):
        self._td.cleanup()

    def test_end_to_end_editing_counts(self):
        deleted = AMP1[: GUIDE1_START + 4] + AMP1[GUIDE1_START + 9 :]
        scratch = Path(self._td.name) / "scratch"
        scratch.mkdir()
        fa = valid_single_guide_fasta(scratch / "ref.fa")
        fq = write_fastq(
            scratch / "plantA.fastq",
            [("wt1", AMP1), ("wt2", AMP1), ("del1", deleted), ("del2", deleted)],
        )
        uid = self.client.post("/api/uploads").json()["upload_id"]
        self.client.put(
            f"/api/uploads/{uid}/files/ref.fa?chunk=0&chunks=1",
            content=fa.read_bytes(),
        )
        self.client.put(
            f"/api/uploads/{uid}/files/plantA.fastq?chunk=0&chunks=1",
            content=fq.read_bytes(),
        )
        job_id = self.client.post(
            "/api/jobs",
            json={
                "upload_id": uid,
                "fasta": "ref.fa",
                "fastqs": ["plantA.fastq"],
            },
        ).json()["id"]
        status = _wait_status(self.client, job_id, timeout=10)
        self.assertEqual(status["status"], "done", status)
        results = self.client.get(f"/api/jobs/{job_id}/results").json()
        self.assertEqual(results["samples"][0]["sample_name"], "plantA")
        self.assertEqual(results["samples"][0]["n_assigned"], 4)
        eff = results["efficiencies"][0]
        self.assertEqual(eff["guide"], GUIDE1_NAME)
        self.assertEqual(eff["wt_unedited"], 2)
        self.assertEqual(eff["edited_deletion_small"], 2)
        self.assertEqual(eff["pct_editing"], 50.0)

    def test_download_unassigned_fastq(self):
        junk = random_dna(len(AMP1), seed=7)
        scratch = Path(self._td.name) / "scratch2"
        scratch.mkdir()
        fa = valid_single_guide_fasta(scratch / "ref.fa")
        fq = write_fastq(
            scratch / "mix.fastq",
            [("wt", AMP1), ("junk", junk)],
        )
        uid = self.client.post("/api/uploads").json()["upload_id"]
        self.client.put(
            f"/api/uploads/{uid}/files/ref.fa?chunk=0&chunks=1",
            content=fa.read_bytes(),
        )
        self.client.put(
            f"/api/uploads/{uid}/files/mix.fastq?chunk=0&chunks=1",
            content=fq.read_bytes(),
        )
        job_id = self.client.post(
            "/api/jobs",
            json={
                "upload_id": uid,
                "fasta": "ref.fa",
                "fastqs": ["mix.fastq"],
            },
        ).json()["id"]
        status = _wait_status(self.client, job_id, timeout=10)
        self.assertEqual(status["status"], "done", status)
        results = self.client.get(f"/api/jobs/{job_id}/results").json()
        self.assertEqual(results["samples"][0]["n_unassigned"], 1)
        exports = results["unassigned_exports"]
        self.assertEqual(len(exports), 1)
        self.assertEqual(exports[0]["n_reads"], 1)
        res = self.client.get(f"/api/jobs/{job_id}/unassigned/mix")
        self.assertEqual(res.status_code, 200)
        self.assertIn("application/x-fastq", res.headers.get("content-type", ""))
        with tempfile.NamedTemporaryFile(suffix=".fq") as tmp:
            tmp.write(res.content)
            tmp.flush()
            reads = parse_fastq(tmp.name)
        self.assertEqual(reads, [("junk", junk)])
