import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest.mock import patch

import benchmark


class FileHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.calls += 1
        if self.path == "/missing":
            self.send_error(404)
            return

        # Change the size on each request. Some responses end at EOF without a length.
        body = b"x" * (70_000 + self.server.calls)
        self.send_response(200)
        if self.path == "/short":
            self.send_header("Content-Length", str(len(body) + 1))
        elif self.server.calls % 2 == 0:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), FileHandler)
        self.server.calls = 0
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02})
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(self.server.shutdown)

    def test_full_downloads_and_units(self):
        out = io.StringIO()
        # Simulated elapsed times 1 through 10 seconds. HTTP and body reads are real.
        ticks = [tick for n in range(1, 11) for tick in (20 * n, 21 * n)]
        with patch.object(benchmark, "perf_counter", side_effect=ticks), redirect_stdout(out):
            status = benchmark.main([self.base_url + "/file"])
        self.assertEqual(status, 0)
        self.assertEqual(self.server.calls, 10)
        result = out.getvalue()
        self.assertIn("Среднее время запроса: 5500.00 мс", result)
        self.assertIn("Скачано всего: 700055 байт", result)
        self.assertIn("Скорость скачивания: 0.102 Мбит/с", result)

    def check_failed_download(self, path, reason):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = benchmark.main([self.base_url + path])
        self.assertNotEqual(status, 0)
        self.assertEqual(self.server.calls, 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn(reason, err.getvalue())

    def test_short_body(self):
        self.check_failed_download("/short", "неполный ответ")

    def test_http_error(self):
        self.check_failed_download("/missing", "404")


if __name__ == "__main__":
    unittest.main()
