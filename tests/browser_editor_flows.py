"""Editor/import/export browser flows. Isolated contexts and read-only HTTP fixture routes.
Run: PLAYWRIGHT_CHANNEL=chrome /opt/anaconda3/bin/python3 tests/browser_editor_flows.py -v
"""
import json
import os
import sys
import threading
import unittest
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = {"id": "editor_fixture", "title": "Editor fixture", "description": "Original",
           "cards": [{"id": "stable-a", "term": "apple", "definition": "fruit", "image": "https://example.org/apple.png"},
                     {"id": "stable-b", "term": "pear", "definition": "fruit", "image": ""}]}


class ReadOnlyHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.send_error(405)


class BrowserEditorFlows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(ReadOnlyHandler, directory=str(ROOT)))
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
        cls.url = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def setUp(self):
        self.context = self.browser.new_context(service_workers="block")
        self.context.route("https://**/*", lambda r: r.abort())
        self.context.route("**/api/sets", lambda r: r.fulfill(json=[]))
        self.context.route("**/data/sets.json", lambda r: r.fulfill(json=[]))
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("dialog", lambda dialog: dialog.accept())
        self.page.add_init_script("localStorage.setItem('qp_settings',JSON.stringify({autoSound:false}));")
        self.page.goto(self.url)
        self.page.wait_for_function("window.appReady === true")

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def seed(self):
        self.page.evaluate("async s => {await saveCustomSet(s); await loadSetsList(s.id);}", FIXTURE)

    def create(self):
        self.page.evaluate("showCreateSetView()")

    def drafts(self):
        return self.page.evaluate("getEditorDrafts()")

    def test_add_remove_and_import_autosave(self):
        self.create()
        self.page.locator("#create-title").fill("Draft")
        self.page.locator(".add-card-btn").click()
        self.assertEqual(len(self.drafts()["new"]["cards"]), 6)
        self.page.locator("#create-cards-list .btn-icon").last.click()
        self.assertEqual(len(self.drafts()["new"]["cards"]), 5)
        self.page.locator(".import-btn-inline").click()
        self.page.locator("#table-import-text").fill("Term\tDefinition\na\tb\nc\td")
        self.page.locator("#table-import-submit").click()
        draft = self.drafts()["new"]
        self.assertEqual([c["term"] for c in draft["cards"]], ["a", "c"])
        self.page.reload()
        self.page.wait_for_function("window.appReady === true")
        expect(self.page.locator(".term-input")).to_have_count(2)
        expect(self.page.locator(".term-input").first).to_have_value("a")

    def test_csv_file_import_maps_extra_column_into_definition(self):
        self.page.evaluate("openTableImporter('new')")
        payload = b'Term,Definition,Example\r\n"hello, world",greeting,"says \"\"hello\"\""\r\n'
        self.page.locator("#table-import-file").set_input_files({
            "name": "cards.csv", "mimeType": "text/csv", "buffer": payload
        })
        self.page.wait_for_function("document.getElementById('table-import-count').textContent === '1'")
        self.page.locator("#table-import-column-map select").nth(2).select_option("definition-extra")
        self.page.locator("#table-import-title").fill("Imported CSV")
        self.page.locator("#table-import-submit").click()
        self.page.wait_for_function("currentSet?.title === 'Imported CSV'")
        self.assertEqual(self.page.evaluate("currentSet.cards[0].term"), "hello, world")
        self.assertEqual(self.page.evaluate("currentSet.cards[0].definition"), 'greeting\nExample: says "hello"')

    def test_xlsx_import_selects_a_sheet_in_browser(self):
        self.page.evaluate("""() => { window.XLSX = {
            read: () => ({ SheetNames: ['First', 'Second'], Sheets: {
                First: [['Term', 'Definition'], ['one', 'một']],
                Second: [['Term', 'Definition'], ['two', 'hai']]
            }}),
            utils: { sheet_to_json: sheet => sheet }
        }}""")
        self.page.evaluate("openTableImporter('new')")
        self.page.locator("#table-import-file").set_input_files({
            "name": "cards.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "buffer": b"fake xlsx"
        })
        expect(self.page.locator("#table-import-sheet-wrap")).to_be_visible()
        self.page.locator("#table-import-sheet").select_option("1")
        self.assertIn("two", self.page.locator("#table-import-preview").inner_text())

    def test_mobile_import_modal_accepts_pasted_table(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.locator(".mob-nav-create").click()
        expect(self.page.locator("#table-import-modal")).to_be_visible()
        self.page.locator("#table-import-text").fill("Term\tDefinition\nphone\tđiện thoại")
        self.assertLessEqual(
            self.page.locator("#table-import-modal .modal-content").evaluate("el => el.scrollWidth"),
            self.page.locator("#table-import-modal .modal-content").evaluate("el => el.clientWidth")
        )
        self.page.locator("#table-import-submit").click()
        self.page.wait_for_function("currentSet?.cards?.[0]?.term === 'phone'")

    def test_invalid_text_replaces_previous_valid_preview(self):
        self.page.evaluate("openTableImporter('new')")
        text = self.page.locator("#table-import-text")
        text.fill("Term\tDefinition\nvalid\tvalue")
        expect(self.page.locator("#table-import-submit")).to_be_enabled()
        text.fill('"unclosed')
        expect(self.page.locator("#table-import-error")).to_be_visible()
        expect(self.page.locator("#table-import-submit")).to_be_disabled()
        expect(self.page.locator("#table-import-count")).to_have_text("0")

    def test_empty_draft_is_removed(self):
        self.create()
        self.page.locator("#create-title").fill("Transient")
        self.page.locator("#create-title").fill("")
        self.assertNotIn("new", self.drafts())
        self.assertIsNone(self.page.evaluate("localStorage.getItem('qp_active_draft')"))

    def test_create_set_persists_in_indexeddb_after_reload(self):
        self.create()
        self.page.locator("#create-title").fill("Saved set")
        self.page.locator(".term-input").first.fill("hello")
        self.page.locator(".def-input").first.fill("xin chào")
        self.page.locator("#btn-save-set-top").click()
        self.page.wait_for_function("currentSet?.title === 'Saved set'")
        set_id = self.page.evaluate("currentSet.id")
        saved = self.page.evaluate("id => Database.getSetById(id)", set_id)
        self.assertEqual(saved["cards"][0]["term"], "hello")
        self.page.reload()
        self.page.wait_for_function("window.appReady === true")
        self.assertEqual(self.page.evaluate("id => Database.getSetById(id).then(s=>s.title)", set_id), "Saved set")

    def test_draft_discard_and_active_key(self):
        self.create()
        self.page.locator("#create-title").fill("Disposable")
        self.page.evaluate("showDashboard()")
        self.page.locator("#draft-banner button[title='Bỏ bản nháp']").click()
        self.assertEqual(self.drafts(), {})

    def test_import_separator_draft_restored(self):
        self.create()
        self.page.evaluate("document.getElementById('import-box-ui').style.display = 'block'")
        self.page.locator("#termSepCustom").fill("=>")
        self.page.locator("#cardSepCustom").fill("||")
        self.page.locator("#import-raw-text").fill("a=>b=>c||d=>e")
        self.page.reload()
        self.page.wait_for_function("window.appReady === true")
        expect(self.page.locator("#termSepCustom")).to_have_value("=>")
        expect(self.page.locator("#preview-count")).to_have_text("2")
        self.page.locator("#import-box-ui .btn-primary").click()
        expect(self.page.locator(".def-input").first).to_have_value("b=>c")

    def test_invalid_import_does_not_insert_partial_rows(self):
        self.create()
        self.page.evaluate("document.getElementById('import-box-ui').style.display = 'block'")
        self.page.locator("#import-raw-text").fill("valid\tdefinition\nbroken")
        self.page.locator("#import-box-ui .btn-primary").click()
        expect(self.page.locator(".term-input").first).to_have_value("")
        expect(self.page.locator("#import-raw-text")).to_have_value("valid\tdefinition\nbroken")

    def test_edit_image_id_and_progress_survive_draft(self):
        self.seed()
        self.page.evaluate("async()=>{await Database.setCardBox('editor_fixture','stable-a',3,true); openEditCurrentSet();}")
        self.page.locator(".term-input").first.fill("green apple")
        expect(self.page.locator(".image-input").first).to_have_value(FIXTURE["cards"][0]["image"])
        self.page.locator(".image-input").first.fill("https://example.org/green.png")
        self.page.reload()
        self.page.wait_for_function("window.appReady === true")
        self.page.locator("#btn-save-set-top").click()
        self.page.wait_for_function("document.getElementById('create-set-view').style.display === 'none'")
        saved = self.page.evaluate("Database.getSetById('editor_fixture')")
        self.assertEqual(saved["cards"][0]["id"], "stable-a")
        self.assertEqual(saved["cards"][0]["image"], "https://example.org/green.png")
        self.assertEqual(saved["cards"][0]["term"], "green apple")
        progress = self.page.evaluate("Database.getProgress('editor_fixture')")
        self.assertEqual(progress[0]["box"], 3)
        self.assertTrue(progress[0]["isStarred"])
        self.assertNotIn("editor_fixture", self.drafts())

    def test_new_editor_has_no_stale_import(self):
        self.seed()
        self.create()
        self.page.evaluate("document.getElementById('import-box-ui').style.display = 'block'")
        self.page.locator("#import-raw-text").fill("stale\ttext")
        self.page.evaluate("showDashboard(); openEditCurrentSet()")
        expect(self.page.locator("#import-raw-text")).to_have_value("")
        expect(self.page.locator("#preview-count")).to_have_text("0")

    def test_failed_save_keeps_editor_and_draft(self):
        self.create()
        self.page.locator(".term-input").first.fill("a")
        self.page.locator(".def-input").first.fill("b")
        self.page.evaluate("() => { Database.saveSet = async()=>{throw new Error('disk full')}; }")
        self.page.locator("#btn-save-set-top").click()
        expect(self.page.locator("#create-set-view")).to_be_visible()
        expect(self.page.locator("#btn-save-set-top")).to_be_enabled()
        self.assertEqual(self.drafts()["new"]["cards"][0]["term"], "a")
        self.assertIn("Không lưu được", self.page.locator("#toast-msg").inner_text())

    def test_failed_plain_import_returns_false(self):
        result = self.page.evaluate("async()=>{Database.saveSet=async()=>{throw new Error('disk full')}; return parseAndImportText('a\\tb')}")
        self.assertFalse(result)

    def test_separator_modes_and_literal_metacharacters(self):
        cases = [
            ("comma", "newline", "", "", "a,b,c\r\nd,e", ["b,c", "e"]),
            ("tab", "semicolon", "", "", "a\tb;c\td", ["b", "d"]),
            ("custom", "custom", ".*", "[x]", "a.*b.*c[x]d.*e", ["b.*c", "e"]),
        ]
        self.create()
        for term_mode, card_mode, term_custom, card_custom, text, definitions in cases:
            with self.subTest(term_mode=term_mode, card_mode=card_mode):
                self.page.evaluate("""args => {
                    document.querySelector(`input[name=termSep][value=${args[0]}]`).checked=true;
                    document.querySelector(`input[name=cardSep][value=${args[1]}]`).checked=true;
                    document.getElementById('termSepCustom').value=args[2];
                    document.getElementById('cardSepCustom').value=args[3];
                    document.getElementById('import-raw-text').value=args[4];
                    updateImportPreview();
                }""", [term_mode, card_mode, term_custom, card_custom, text])
                self.assertEqual(self.page.evaluate("parsedImportCards.map(c=>c.def)"), definitions)
                self.assertEqual(self.page.evaluate("invalidImportRows"), [])

    def test_delete_first_card_preserves_surviving_id_progress_and_remove_image(self):
        self.seed()
        self.page.evaluate("async()=>{await Database.setCardBox('editor_fixture','stable-b',2,true); openEditCurrentSet()}")
        self.page.locator("#create-cards-list .btn-icon").first.click()
        self.page.locator(".image-input").fill("https://example.org/pear.png")
        self.page.locator(".image-input").fill("")
        self.page.locator("#btn-save-set-top").click()
        self.page.wait_for_function("document.getElementById('create-set-view').style.display === 'none'")
        saved = self.page.evaluate("Database.getSetById('editor_fixture')")
        self.assertEqual([c["id"] for c in saved["cards"]], ["stable-b"])
        self.assertEqual(saved["cards"][0]["image"], "")
        self.assertEqual(self.page.evaluate("(async()=> (await Database.getProgress('editor_fixture'))[0].box)()"), 2)

    def test_invalid_image_url_does_not_silently_drop_image(self):
        self.seed()
        self.page.evaluate("openEditCurrentSet()")
        self.page.locator(".image-input").first.fill("javascript:alert(1)")
        self.page.locator("#btn-save-set-top").click()
        expect(self.page.locator("#create-set-view")).to_be_visible()
        self.assertEqual(self.page.evaluate("(async()=> (await Database.getSetById('editor_fixture')).cards[0].image)()"), FIXTURE["cards"][0]["image"])
        self.assertIn("Đường dẫn ảnh", self.page.locator("#toast-msg").inner_text())

    def test_json_file_import_roundtrip_and_failure_retains_source(self):
        payload = json.dumps(FIXTURE).encode()
        self.page.locator("#import-json-file").set_input_files({"name": "fixture.json", "mimeType": "application/json", "buffer": payload})
        self.page.wait_for_function("currentSet?.id === 'editor_fixture'")
        self.assertEqual(self.page.evaluate("currentSet.cards.map(c=>c.id)"), ["stable-a", "stable-b"])
        self.page.evaluate("() => {Database.saveSet=async()=>{throw new Error('disk full')}}")
        imported = dict(FIXTURE, id="failed_import")
        self.page.locator("#import-json-file").set_input_files({"name": "failed.json", "mimeType": "application/json", "buffer": json.dumps(imported).encode()})
        expect(self.page.locator("#toast-msg")).to_contain_text("Không thể nhập")
        self.assertIsNone(self.page.evaluate("Database.getSetById('failed_import')"))
        self.assertEqual(self.page.evaluate("currentSet.id"), "editor_fixture")

    def test_clear_other_draft_keeps_active_draft(self):
        self.create()
        self.page.locator("#create-title").fill("Keep active")
        self.page.evaluate("clearEditorDraft('unrelated')")
        self.assertEqual(self.page.evaluate("localStorage.getItem('qp_active_draft')"), "new")

    def test_export_uses_full_set_not_filtered_state(self):
        self.seed()
        self.page.evaluate("cardsState = cardsState.slice(0,1)")
        with self.page.expect_download() as download:
            self.page.evaluate("exportCurrentSet()")
        data = json.loads(Path(download.value.path()).read_text())
        self.assertEqual(len(data["cards"]), 2)
        self.assertEqual(data["cards"][0]["image"], FIXTURE["cards"][0]["image"])

    def test_export_failure_is_not_reported_as_success(self):
        self.seed()
        self.page.evaluate("URL.createObjectURL=()=>{throw new Error('download unavailable')}; Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw new Error('denied')}}})")
        self.assertFalse(self.page.evaluate("exportCurrentSet()"))
        self.assertNotIn("Đã xuất", self.page.locator("#toast-msg").inner_text())


if __name__ == "__main__":
    unittest.main()
