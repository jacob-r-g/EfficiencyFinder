import os
import tempfile
import time
import unittest
from pathlib import Path

from web.backend.store import MAX_CHUNK_BYTES, RESULT_TTL_S, Store, StoreError


class TestStore(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._td.name))

    def tearDown(self):
        self._td.cleanup()

    def test_rejects_path_in_filename(self):
        uid = self.store.new_upload_id()
        with self.assertRaises(StoreError):
            self.store.write_chunk(uid, "../etc/passwd", 0, 1, b"x")
        with self.assertRaises(StoreError):
            self.store.write_chunk(uid, "bad name.fq", 0, 1, b"x")

    def test_assembles_chunks_in_order(self):
        uid = self.store.new_upload_id()
        self.assertFalse(self.store.write_chunk(uid, "a.fq", 1, 2, b"BB"))
        self.assertTrue(self.store.write_chunk(uid, "a.fq", 0, 2, b"AA"))
        files = self.store.assembled_files(uid)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_bytes(), b"AABB")

    def test_rejects_oversized_chunk(self):
        uid = self.store.new_upload_id()
        with self.assertRaises(StoreError):
            self.store.write_chunk(uid, "a.fq", 0, 1, b"x" * (MAX_CHUNK_BYTES + 1))

    def test_move_upload_into_job_and_delete_inputs(self):
        uid = self.store.new_upload_id()
        self.store.write_chunk(uid, "ref.fa", 0, 1, b">x\nACGT\n")
        jid = self.store.new_job_id()
        dest = self.store.move_upload_into_job(uid, jid)
        self.assertEqual((dest / "ref.fa").read_bytes(), b">x\nACGT\n")
        with self.assertRaises(StoreError):
            self.store.upload_path(uid)
        self.store.delete_job_inputs(jid)
        self.assertFalse(dest.exists())

    def test_expire_removes_stale_jobs(self):
        jid = self.store.new_job_id()
        path = self.store.job_path(jid)
        old = time.time() - RESULT_TTL_S - 10
        os.utime(path, (old, old))
        self.store.expire(now=time.time())
        with self.assertRaises(StoreError):
            self.store.job_path(jid)
