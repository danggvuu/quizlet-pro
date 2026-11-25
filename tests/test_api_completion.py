"""API persistence/security regressions, all writes and network calls isolated."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import server


class QuietHandler(server.handler):
    def log_message(self, *args):
        pass


class APICompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.data = self.base / 'data' / 'sets'
        self.data.mkdir(parents=True)
        (self.base / 'index.html').write_text('<html>isolated shell</html>')
        (self.base / 'data' / 'sets.json').write_text('[]')
        self.patches = [patch.object(server, 'BASE_DIR', self.base),
                        patch.object(server, 'DATA_DIR', self.data), patch.object(server, 'IS_VERCEL', False)]
        for p in self.patches:
            p.start()
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def request(self, method, path, payload=None):
        conn = http.client.HTTPConnection(*self.httpd.server_address, timeout=5)
        conn.request(method, path, json.dumps(payload) if payload is not None else None,
                     {'Content-Type': 'application/json'})
        response = conn.getresponse()
        status, headers, body = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return status, headers, body

    def fixture(self, **changes):
        return {'id': 'test', 'title': 'Test', 'description': 'Mô tả', 'numTerms': 999,
                'sourceWarning': 'Nguồn thiếu một mặt',
                'cards': [{'id': 0, 'term': 'hello', 'definition': 'xin chào'}], **changes}

    def write_set(self, data):
        (self.data / f'{data["id"]}.json').write_text(json.dumps(data), encoding='utf-8')

    def test_import_round_trip_manifest_counts_and_source_warning(self):
        status, _, body = self.request('POST', '/api/manual-import', self.fixture())
        self.assertEqual(status, 200)
        saved = json.loads(body)['set']
        self.assertEqual(saved['numTerms'], 1)
        self.assertEqual(saved['cards'][0]['id'], 0)
        self.assertEqual(json.loads(self.request('GET', '/api/sets/test')[2]), saved)
        summary = json.loads(self.request('GET', '/api/sets')[2])['sets'][0]
        self.assertEqual(summary['sourceWarning'], saved['sourceWarning'])
        self.assertEqual(json.loads((self.base / 'data' / 'sets.json').read_text()), [summary])

    def test_corrupt_and_wrong_schema_files_report_errors_without_disconnect(self):
        for content in ['{bad', '[]', '{"cards":null}', json.dumps(self.fixture(id='different'))]:
            (self.data / 'test.json').write_text(content)
            status, headers, body = self.request('GET', '/api/sets/test')
            self.assertEqual(status, 500)
            self.assertEqual(json.loads(body)['status'], 'error')
            self.assertEqual(headers['Cache-Control'], 'no-store')
            listing = json.loads(self.request('GET', '/api/sets')[2])
            self.assertEqual(listing['sets'], [])
            self.assertEqual(listing['warnings'][0]['id'], 'test')

    def test_legacy_partial_card_retained_but_stale_count_fixed(self):
        self.write_set(self.fixture(cards=[{'id': 0, 'term': 'word', 'definition': ''}]))
        loaded = json.loads(self.request('GET', '/api/sets/test')[2])
        self.assertEqual(loaded['numTerms'], 1)
        self.assertEqual(loaded['cards'][0]['definition'], '')
        self.assertEqual(json.loads(self.request('GET', '/api/sets')[2])['sets'][0]['numTerms'], 1)

    def test_head_matches_get_headers_and_never_returns_body(self):
        self.write_set(self.fixture())
        for path in ['/', '/index.html', '/api/health', '/api/sets', '/api/sets/test', '/api/missing']:
            get_status, get_headers, get_body = self.request('GET', path)
            status, headers, body = self.request('HEAD', path)
            self.assertEqual(status, get_status, path)
            self.assertEqual(body, b'', path)
            self.assertEqual(headers['Content-Length'], str(len(get_body)), path)
            self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')

    def test_manifest_rebuilt_after_corruption_or_wrong_schema(self):
        self.write_set(self.fixture(id='previous'))
        manifest = self.base / 'data' / 'sets.json'
        for invalid in ['not json', '{}', '[null]']:
            manifest.write_text(invalid)
            self.assertEqual(self.request('POST', '/api/manual-import', self.fixture())[0], 200)
            restored = json.loads(manifest.read_text())
            self.assertEqual({s['id'] for s in restored}, {'previous', 'test'})
            self.assertTrue(all(s['numTerms'] == 1 and s['sourceWarning'] for s in restored))

    def test_manifest_write_failure_is_visible_without_losing_saved_set(self):
        original = server.atomic_write_json
        def fail_manifest(path, value):
            if Path(path).name == 'sets.json':
                raise PermissionError('read only manifest')
            return original(path, value)
        with patch.object(server, 'atomic_write_json', side_effect=fail_manifest):
            status, _, body = self.request('POST', '/api/manual-import', self.fixture())
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)['warning'])
        self.assertTrue((self.data / 'test.json').exists())

    def test_invalid_metadata_and_nonstandard_json_cannot_mutate_files(self):
        for changes in [{'description': {}}, {'sourceWarning': []}, {'id': True}, {'id': []},
                        {'cards': [{'id': float('nan'), 'term': 'a', 'definition': 'b'}]}]:
            self.assertEqual(self.request('POST', '/api/manual-import', self.fixture(**changes))[0], 400)
        self.assertEqual(list(self.data.glob('*')), [])

    def test_zero_set_id_is_preserved(self):
        status, _, body = self.request('POST', '/api/manual-import', self.fixture(id=0))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['set']['id'], '0')

    def test_static_and_api_symlinks_cannot_escape_public_root(self):
        with tempfile.TemporaryDirectory() as outside:
            secret = Path(outside) / 'private.json'
            secret.write_text(json.dumps(self.fixture()))
            (self.data / 'test.json').symlink_to(secret)
            (self.base / 'index.html').unlink()
            (self.base / 'index.html').symlink_to(secret)
            for path in ['/', '/index.html', '/data/sets/test.json', '/api/sets/test', '/server.py', '/.git/config']:
                self.assertEqual(self.request('GET', path)[0], 404, path)
                self.assertEqual(self.request('HEAD', path)[0], 404, path)

    def test_missing_index_and_asset_directory_do_not_expose_listings(self):
        (self.base / 'index.html').unlink()
        (self.base / 'sw.js').mkdir()
        (self.base / 'sw.js' / 'private.txt').write_text('secret')
        for path in ['/', '/sw.js']:
            self.assertEqual(self.request('GET', path)[0], 404)
            self.assertEqual(self.request('HEAD', path)[0], 404)

    def test_missing_manifest_recovers_existing_sets(self):
        self.write_set(self.fixture(id='previous'))
        manifest = self.base / 'data' / 'sets.json'
        manifest.unlink()
        self.assertEqual(self.request('POST', '/api/manual-import', self.fixture())[0], 200)
        self.assertEqual({s['id'] for s in json.loads(manifest.read_text())}, {'previous', 'test'})

    def test_encoded_valid_set_id_is_decoded(self):
        self.write_set(self.fixture())
        self.assertEqual(self.request('GET', '/api/sets/%74est')[0], 200)
        self.assertEqual(self.request('GET', '/api/sets/test%2Fother')[0], 400)

    def test_scrape_rejects_invalid_url_and_ids_in_query_or_credentials(self):
        with patch.object(server, 'scrape_quizlet') as scrape:
            for url in ['https://[bad', 'https://quizlet.com/not-a-set?next=123456',
                        'https://123456@quizlet.com/no-set', 'https://quizlet.com/classes/123456']:
                self.assertEqual(self.request('POST', '/api/scrape', {'url': url})[0], 400, url)
            scrape.assert_not_called()

    def test_tts_upstream_failure_returns_json_for_get_and_head(self):
        with patch.object(server.urllib.request, 'urlopen', side_effect=OSError('offline')):
            status, headers, body = self.request('GET', '/api/tts?q=hello')
            self.assertEqual(status, 502)
            self.assertEqual(json.loads(body)['status'], 'error')
            status, head_headers, head_body = self.request('HEAD', '/api/tts?q=hello')
            self.assertEqual(status, 502)
            self.assertEqual(head_body, b'')
            self.assertEqual(head_headers['Content-Length'], headers['Content-Length'])
        self.assertEqual(self.request('GET', '/api/tts')[0], 400)

    def test_scrape_mocked_and_tts_invalid_language_never_calls_network(self):
        with patch.object(server, 'scrape_quizlet', return_value=self.fixture()) as scrape:
            status, _, body = self.request('POST', '/api/scrape', {'url': 'https://quizlet.com/123456/test/'})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['set']['title'], 'Test')
            scrape.assert_called_once_with('123456', raw_url='https://quizlet.com/123456/test/')
        with patch.object(server.urllib.request, 'urlopen') as network:
            self.assertEqual(self.request('GET', '/api/tts?q=hello&tl=en%26q%3Devil')[0], 400)
            network.assert_not_called()


if __name__ == '__main__':
    unittest.main()
