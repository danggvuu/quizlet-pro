import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch
import server


def page(ids, total, token=None, status=200):
    response = Mock(status_code=status)
    response.json.return_value = {"responses": [{
        "models": {"studiableItem": [{"id": i} for i in ids]},
        "paging": {"total": total, "token": token},
    }]}
    return response


class PaginationTests(unittest.TestCase):
    def test_cursor_is_encoded_and_all_pages_loaded(self):
        client = Mock()
        client.get.side_effect = [page([1, 2], 3, "a+b/="), page([3], 3)]
        self.assertEqual(len(server.fetch_studiable_items(client, "123456", {}, {})), 3)
        self.assertIn("pagingToken=a%2Bb%2F%3D", client.get.call_args.args[0])

    def test_partial_repeated_and_failed_pages_are_rejected(self):
        for responses in [
            [page([1], 2)],
            [page([1], 2, "next"), page([1], 2)],
            [page([1], 2, "next"), page([], 2, status=403)],
        ]:
            with self.subTest(responses=responses):
                client = Mock()
                client.get.side_effect = responses
                with self.assertRaises(ValueError):
                    server.fetch_studiable_items(client, "123456", {}, {})


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def request(self, method, path, payload=None, headers=None):
        conn = http.client.HTTPConnection(*self.httpd.server_address, timeout=5)
        body = json.dumps(payload) if payload is not None else None
        conn.request(method, path, body, headers or {"Content-Type": "application/json"})
        response = conn.getresponse()
        status, data = response.status, response.read()
        conn.close()
        return status, data

    def test_assets_available_but_source_and_git_not_served(self):
        for path in ["/", "/js/study-utils.js", "/data/sets.json", "/sw.js", "/api/health"]:
            self.assertEqual(self.request("GET", path)[0], 200)
        for path in ["/server.py", "/.git/config", "/js/../server.py"]:
            self.assertEqual(self.request("GET", path)[0], 404)

    def test_static_assets_revalidate_for_get_head_and_conditional_requests(self):
        paths = ["/", "/index.html", "/sw.js", "/js/session.js?v=6", "/data/sets.json"]
        for method in ("GET", "HEAD"):
            for path in paths:
                with self.subTest(method=method, path=path):
                    conn = http.client.HTTPConnection(*self.httpd.server_address, timeout=5)
                    conn.request(method, path)
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    expected = "no-store, max-age=0" if path == "/sw.js" else "no-cache, max-age=0, must-revalidate"
                    self.assertEqual(response.getheader("Cache-Control"), expected)
                    modified = response.getheader("Last-Modified")
                    response.read()
                    conn.request(method, path, headers={"If-Modified-Since": modified})
                    response = conn.getresponse()
                    self.assertEqual(response.status, 304)
                    self.assertEqual(response.getheader("Cache-Control"), expected)
                    response.read()
                    conn.close()

    def test_invalid_imports_and_urls(self):
        for payload in [[], {"cards": "wrong"}, {"cards": [{}], "id": "../escape"}]:
            self.assertEqual(self.request("POST", "/api/manual-import", payload)[0], 400)
        for url in ["https://quizlet.com.evil.test/123456", "file:///123456", 123456]:
            self.assertEqual(self.request("POST", "/api/scrape", {"url": url})[0], 400)
        self.assertEqual(self.request("GET", "/api/sets/../../sets")[0], 400)

    def test_cross_origin_and_non_json_writes_are_rejected(self):
        payload = {"cards": [{"term": "a", "definition": "b"}]}
        status, _ = self.request("POST", "/api/manual-import", payload, {
            "Content-Type": "application/json", "Origin": "https://unrelated.example"})
        self.assertEqual(status, 403)
        status, _ = self.request("POST", "/api/manual-import", payload, {"Content-Type": "text/plain"})
        self.assertEqual(status, 415)

    def test_blank_sides_and_duplicate_ids_are_rejected(self):
        payloads = [
            {"cards": [{"term": "a", "definition": ""}]},
            {"cards": [{"id": "x", "term": "a", "definition": "b"},
                       {"id": "x", "term": "c", "definition": "d"}]},
        ]
        for payload in payloads:
            self.assertEqual(self.request("POST", "/api/manual-import", payload)[0], 400)

    def test_manual_import_writes_and_returns_set(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(server, "DATA_DIR", Path(directory)), patch.object(server, "update_manifest"):
                status, body = self.request("POST", "/api/manual-import", {
                    "title": "Test", "cards": [{"id": 0, "term": "a", "definition": "b"}],
                })
                self.assertEqual(status, 200)
                result = json.loads(body)["set"]
                self.assertEqual(result["cards"][0]["id"], 0)
                self.assertEqual(json.loads((Path(directory) / f'{result["id"]}.json').read_text()), result)


if __name__ == "__main__":
    unittest.main()
