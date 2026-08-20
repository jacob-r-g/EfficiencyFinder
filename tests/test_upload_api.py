import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from web.backend.app import create_app
from web.backend.store import Store


class TestUploadApi(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._td.name))
        self.client = TestClient(create_app(self.store))

    def tearDown(self):
        self._td.cleanup()

    def test_health(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok"})

    def test_chunked_upload_assembles_file(self):
        uid = self.client.post("/api/uploads").json()["upload_id"]
        first = self.client.put(
            f"/api/uploads/{uid}/files/a.fq?chunk=0&chunks=2",
            content=b"AA",
        )
        self.assertEqual(first.json(), {"assembled": False})
        second = self.client.put(
            f"/api/uploads/{uid}/files/a.fq?chunk=1&chunks=2",
            content=b"BB",
        )
        self.assertEqual(second.json(), {"assembled": True})
        files = self.store.assembled_files(uid)
        self.assertEqual(files[0].read_bytes(), b"AABB")

    def test_rejects_bad_filename(self):
        uid = self.client.post("/api/uploads").json()["upload_id"]
        res = self.client.put(
            f"/api/uploads/{uid}/files/not%20ok.fq?chunk=0&chunks=1",
            content=b"x",
        )
        self.assertEqual(res.status_code, 400)
