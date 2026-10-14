import json
import time
import unittest

from token_usage.adapters.herdr_socket import HerdrSocket
from token_usage.ports import HerdrError
from tests.adapters.herdr_fakes import FakeServer, fixture_panes, ok_handler


class HerdrSocketTest(unittest.TestCase):
    def serve(self, handler):
        srv = FakeServer(handler)
        self.addCleanup(srv.close)
        return srv

    def test_list_panes_returns_fixture(self):
        srv = self.serve(ok_handler)
        self.assertEqual(HerdrSocket(srv.path).list_panes(), fixture_panes())

    def test_error_response(self):
        def h(req, conn):
            conn.sendall(json.dumps({"id": "req_1", "error": {"code": "x", "message": "m"}}).encode() + b"\n")
        with self.assertRaises(HerdrError):
            HerdrSocket(self.serve(h).path).list_panes()

    def test_mismatched_id(self):
        def h(req, conn):
            conn.sendall(json.dumps({"id": "other", "result": {"panes": []}}).encode() + b"\n")
        with self.assertRaises(HerdrError):
            HerdrSocket(self.serve(h).path).list_panes()

    def test_close_without_newline(self):
        with self.assertRaises(HerdrError):
            HerdrSocket(self.serve(lambda req, conn: conn.sendall(b'{"id":')).path).list_panes()

    def test_oversized(self):
        def h(req, conn):
            conn.sendall(b"x" * 4096)
            conn.sendall(b"x" * 4096)
        with self.assertRaises(HerdrError):
            HerdrSocket(self.serve(h).path, max_bytes=4096).list_panes()

    def test_never_responds_times_out(self):
        with self.assertRaises(HerdrError):
            HerdrSocket(self.serve(lambda req, conn: time.sleep(1)).path, timeout=0.2).list_panes()

    def test_connect_failure(self):
        with self.assertRaises(HerdrError):
            HerdrSocket("/tmp/definitely-missing.sock").list_panes()


if __name__ == "__main__":
    unittest.main()
