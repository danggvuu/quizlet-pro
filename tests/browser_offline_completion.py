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
        # Resolve macOS /var -> /private/var so containment checks use canonical paths.
        self.root = Path(self.temp.name).resolve()
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
        self.assertEqual(self.page.evaluate("fetch('/js/database.js?v=8').then(r=>r.status)"), 200)
        self.assertEqual(self.page.evaluate("fetch('/js/database.js?v=old').then(r=>r.status)"), 503)

    def test_malformed_manifest_does_not_prevent_shell_control_or_offline_reload(self):
        (self.root / 'data' / 'sets.json').write_text('{bad')
        self.ready()
        self.context.set_offline(True)
        self.page.reload()
        self.page.wait_for_function('window.appReady === true')
        self.assertTrue(self.page.evaluate('!!navigator.serviceWorker.controller'))
        self.assertEqual(self.page.evaluate("fetch('/js/study-utils.js?v=8').then(r=>r.status)"), 200)

    def test_worker_update_reloads_once_and_preserves_answered_position(self):
        worker = (self.root / 'sw.js').read_text()
        index = (self.root / 'index.html').read_text()
        (self.root / 'sw.js').write_text(worker.replace('quizlet-pro-v8', 'quizlet-pro-v5'))
        (self.root / 'index.html').write_text(index.replace('</head>', "<script>window.appRelease='old';</script></head>"))
        self.ready()
        self.page.evaluate("onSetChange('offline_fixture')")
        self.page.wait_for_function("currentSet?.id === 'offline_fixture'")
        self.page.evaluate("handleChoice(currentRoundOptions.indexOf(currentCorrectChoice))")
        other = self.context.new_page()
        other.goto(self.url)
        other.wait_for_function("window.appReady && currentCardIndex === 1")
        navigations = []
        self.page.on('framenavigated', lambda frame: navigations.append(frame.url) if frame == self.page.main_frame else None)
        other_navigations = []
        other.on('framenavigated', lambda frame: other_navigations.append(frame.url) if frame == other.main_frame else None)
        (self.root / 'index.html').write_text(index.replace('</head>', "<script>window.appRelease='new';</script></head>"))
        (self.root / 'sw.js').write_text(worker)
        self.page.evaluate("navigator.serviceWorker.getRegistration().then(registration => registration.update())")
        self.page.wait_for_function("window.appRelease === 'new' && window.appReady && currentCardIndex === 1")
        other.wait_for_function("window.appRelease === 'new' && window.appReady && currentCardIndex === 1")
        self.assertEqual(self.page.evaluate('cardsState[0].mastery'), 1)
        self.assertEqual(len(navigations), 1)
        self.assertEqual(len(other_navigations), 1)
        self.context.set_offline(True)
        cached = self.page.evaluate("fetch('/data/sets/offline_fixture.json').then(response => response.json())")
        self.assertEqual(len(cached['cards']), 2)

    def test_old_production_tab_without_update_listener_also_receives_new_release(self):
        worker = (self.root / 'sw.js').read_text()
        index = (self.root / 'index.html').read_text()
        navigation = (self.root / 'js' / 'navigation.js').read_text()
        legacy_navigation = navigation[:navigation.index("if ('serviceWorker' in navigator)")] + """
            window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js'));
        """
        (self.root / 'sw.js').write_text(worker.replace('quizlet-pro-v8', 'quizlet-pro-v6'))
        (self.root / 'js' / 'navigation.js').write_text(legacy_navigation)
        (self.root / 'index.html').write_text(index.replace('</head>', "<script>window.appRelease='old';</script></head>"))
        self.ready()
        self.page.evaluate("onSetChange('offline_fixture')")
        self.page.wait_for_function("currentSet?.id === 'offline_fixture'")
        self.page.evaluate("handleChoice(currentRoundOptions.indexOf(currentCorrectChoice))")
        (self.root / 'sw.js').write_text(worker)
        (self.root / 'js' / 'navigation.js').write_text(navigation)
        (self.root / 'index.html').write_text(index.replace('</head>', "<script>window.appRelease='new';</script></head>"))
        self.page.evaluate("navigator.serviceWorker.getRegistration().then(registration => registration.update())")
        self.page.wait_for_function("window.appRelease === 'new' && window.appReady && currentCardIndex === 1")
        self.assertEqual(self.page.evaluate('cardsState[0].mastery'), 1)


if __name__ == '__main__':
    unittest.main()
