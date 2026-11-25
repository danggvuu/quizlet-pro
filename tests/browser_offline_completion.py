"""Real isolated Chrome offline regressions. Never uses personal profiles or live cloud."""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from playwright.sync_api import sync_playwright


class QuietHandler(server.handler):
    def log_message(self, *args):
        pass


class OfflineBrowserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        source = Path(server.__file__).parent
        for name in ['index.html', 'sw.js']:
            shutil.copyfile(source / name, self.root / name)
        shutil.copytree(source / 'js', self.root / 'js')
        self.data = self.root / 'data' / 'sets'
        self.data.mkdir(parents=True)
        self.fixture = {'id': 'offline_fixture', 'title': 'Offline fixture', 'numTerms': 2,
                        'cards': [{'id': 0, 'term': 'hello', 'definition': 'xin chào'},
                                  {'id': 1, 'term': 'bye', 'definition': 'tạm biệt'}]}
        (self.data / 'offline_fixture.json').write_text(json.dumps(self.fixture))
        (self.root / 'data' / 'sets.json').write_text(json.dumps([
            {'id': 'offline_fixture', 'title': 'Offline fixture', 'numTerms': 2},
            {'id': 'missing_fixture', 'title': 'Missing fixture', 'numTerms': 1}]))
        self.patches = [patch.object(server, 'BASE_DIR', self.root), patch.object(server, 'DATA_DIR', self.data)]
        for p in self.patches:
            p.start()
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.httpd.server_port}'
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(channel=os.environ.get('PLAYWRIGHT_CHANNEL') or None)
        self.context = self.browser.new_context()
        self.context.route('https://**/*', lambda route: route.abort())
        self.page = self.context.new_page()
        self.page.add_init_script("localStorage.setItem('qp_settings',JSON.stringify({autoSound:false}));")

    def tearDown(self):
        self.context.close()
        self.browser.close()
        self.playwright.stop()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def ready(self):
        self.page.goto(self.url)
        self.page.wait_for_function('window.appReady === true')
        self.page.evaluate('navigator.serviceWorker.ready')
        self.page.wait_for_function('!!navigator.serviceWorker.controller')

    def test_offline_reload_with_query_and_cached_set_despite_missing_preload(self):
        self.ready()
        self.page.evaluate("onSetChange('offline_fixture')")
        self.page.wait_for_function("currentSet?.id==='offline_fixture'")
        self.context.set_offline(True)
        self.page.goto(self.url + '/?offline=1')
        self.page.wait_for_function("window.appReady && currentSet?.id==='offline_fixture'")
        self.assertEqual(self.page.evaluate('cardsState.length'), 2)
        cached = self.page.evaluate("fetch('/data/sets/offline_fixture.json?version=2').then(r=>r.json())")
        self.assertEqual(cached['cards'][0]['id'], 0)
        self.assertEqual(self.page.evaluate("fetch('/js/database.js?version=2').then(r=>r.status)"), 200)

    def test_malformed_manifest_does_not_prevent_shell_control_or_offline_reload(self):
        (self.root / 'data' / 'sets.json').write_text('{bad')
        self.ready()
        self.context.set_offline(True)
        self.page.reload()
        self.page.wait_for_function('window.appReady === true')
        self.assertTrue(self.page.evaluate('!!navigator.serviceWorker.controller'))
        self.assertEqual(self.page.evaluate("fetch('/js/study-utils.js?offline=1').then(r=>r.status)"), 200)


if __name__ == '__main__':
    unittest.main()
