import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

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
