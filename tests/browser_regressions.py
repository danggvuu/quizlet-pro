"""UX regression suite. Real Chrome, isolated storage, no live cloud writes."""
import copy
import json
import os
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import handler
from playwright.sync_api import sync_playwright, expect

FIXTURE = {"id": "audit_a", "title": "Audit A", "description": "Description",
           "cards": [{"id": str(i), "term": f"word{i}", "definition": f"meaning{i}", "image": ""} for i in range(5)]}


class QuietHandler(handler):
    def log_message(self, *args):
        pass


class BrowserRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(channel=os.environ.get("PLAYWRIGHT_CHANNEL") or None)
        cls.url = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def setUp(self):
        self.context = self.browser.new_context(service_workers="block")
        self.context.route("https://**/*", lambda route: route.abort())
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("dialog", lambda dialog: dialog.accept())
        self.page.add_init_script("if (!localStorage.getItem('qp_settings')) localStorage.setItem('qp_settings',JSON.stringify({autoSound:false}));")
        self.page.goto(self.url)
        self.page.wait_for_function("window.appReady === true")

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [], "Unhandled browser errors")

    def seed(self, fixture=FIXTURE):
        self.page.evaluate("async s => {await saveCustomSet(s); await loadSetsList(s.id);}", fixture)

    def cloud_device(self, store, uid="same-user", mobile=False):
        options = {"is_mobile": True, "has_touch": True, "viewport": {"width": 390, "height": 844}} if mobile else {}
        context = self.browser.new_context(service_workers="block", **options)
        context.expose_function("mockCloudList", lambda path: [
            {"id": key.rsplit("/", 1)[1], "value": copy.deepcopy(value)}
            for key, value in store.items() if key.rsplit("/", 1)[0] == path])
        context.expose_function("mockCloudGet", lambda path: copy.deepcopy(store.get(path)))
        context.expose_function("mockCloudPut", lambda path, value: store.__setitem__(path, copy.deepcopy(value)))

        def sdk(route):
            url = route.request.url
            if url.endswith("firebase-app.js"):
                code = "export const initializeApp=()=>({});"
            elif url.endswith("firebase-auth.js"):
                code = "const initialUser=" + json.dumps(uid) + ";" + """
                    const user=id=>id?{uid:id,email:id+'@example.test',
                        displayName:id==='same-user'?'Google Same User':null,
                        photoURL:id==='same-user'?'https://images.example.test/same-user.png':null}:null;
                    const auth={currentUser:user(initialUser)};
                    let observer;
                    export const getAuth=()=>auth;
                    export const onAuthStateChanged=(a,cb)=>{
                        observer=cb;queueMicrotask(()=>cb(a.currentUser));
                    };
                    window.changeCloudUser=id=>{auth.currentUser=user(id);observer(auth.currentUser)};
                    export class GoogleAuthProvider {}
                    export const signInWithPopup=async()=>{
                        if(window.mockLoginError) throw Object.assign(new Error('Login failed'),{code:mockLoginError});
                        changeCloudUser('same-user');return {user:auth.currentUser};
                    };
                    export const signOut=async()=>changeCloudUser(null);
                """
            elif url.endswith("firebase-firestore.js"):
                code = """
                    export const getFirestore=()=>({});
                    export const collection=(db,...parts)=>parts.join('/');
                    export const doc=(db,...parts)=>parts.join('/');
                    export const getDocsFromServer=async path=>({docs:(await mockCloudList(path))
                        .map(item=>({id:item.id,data:()=>item.value}))});
                    const listeners=new Set();
                    window.emitCloudSnapshot=()=>listeners.forEach(cb=>cb({metadata:{fromCache:false,hasPendingWrites:false}}));
                    export const onSnapshot=(path,options,cb)=>{
                        listeners.add(cb);queueMicrotask(()=>emitCloudSnapshot());return ()=>listeners.delete(cb);
                    };
                    export const runTransaction=async(db,fn)=>{
                        const pending=[];
                        const result=await fn({
                            get:async path=>{const value=await mockCloudGet(path);return {exists:()=>!!value,data:()=>value}},
                            set:(path,value)=>pending.push([path,value])
                        });
                        for(const [path,value] of pending) await mockCloudPut(path,value);
                        if(pending.length) queueMicrotask(()=>emitCloudSnapshot());
                        return result;
                    };
                """
            else:
                route.abort()
                return
            route.fulfill(content_type="application/javascript", headers={"Access-Control-Allow-Origin": "*"}, body=code)

        context.route("https://**/*", sdk)
        page = context.new_page()
        page.on("pageerror", lambda error: self.errors.append(str(error)))
        page.add_init_script("localStorage.setItem('qp_settings',JSON.stringify({autoSound:false}));")
        page.goto(self.url)
        page.wait_for_function("window.appReady && window.CloudDB?.accountReady && !cloudSyncRunning")
        return context, page

    def test_same_account_shares_new_sets_and_updates_between_desktop_and_phone(self):
        store = {}
        desktop_context, desktop = self.cloud_device(store)
        phone_context, phone = self.cloud_device(store, mobile=True)
        try:
            desktop.evaluate("showCreateSetView()")
            desktop.locator("#create-title").fill("My shared library")
            desktop.locator(".term-input").first.fill("hello")
            desktop.locator(".def-input").first.fill("xin chào")
            desktop.locator("#btn-save-set-top").click()
            desktop.wait_for_function("currentSet?.title === 'My shared library'")
            set_id = desktop.evaluate("currentSet.id")
            self.assertIn(f"users/same-user/quizlet_sets/{set_id}", store)
            self.assertIsNone(phone.evaluate("id=>Database.getSetById(id)", set_id))
            phone.evaluate("emitCloudSnapshot()")
            phone.wait_for_function("id=>allDashboardSets.some(set=>set.id===id)", arg=set_id)
            phone.locator(f'#dash-sets-grid [data-set-id="{set_id}"]').tap()
            phone.wait_for_function("id=>currentSet?.id===id", arg=set_id)
            self.assertEqual(phone.evaluate("currentSet.cards[0].definition"), "xin chào")
            desktop.evaluate("async()=>{await saveCustomSet({...currentSet,title:'Updated on desktop'});}")
            phone.evaluate("window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}))")
            phone.wait_for_function("!cloudSyncRunning")
            self.assertEqual(phone.evaluate("async id=>(await Database.getSetById(id)).title", set_id), 'Updated on desktop')
            phone.reload()
            phone.wait_for_function("window.appReady && currentSet?.title==='Updated on desktop'")
        finally:
            desktop_context.close()
            phone_context.close()

    def test_mobile_login_uploads_existing_local_library_and_signout_hides_it(self):
        store = {}
        context, page = self.cloud_device(store, uid=None, mobile=True)
        try:
            expect(page.locator('#cloud-account-banner')).to_be_visible()
            self.assertTrue(page.locator('#cloud-account-banner button').evaluate(
                'button=>button.getBoundingClientRect().right<=window.innerWidth'))
            page.evaluate("fixture=>Database.saveSet({...fixture,isCustom:true})", FIXTURE)
            page.evaluate("loadSetsList(null,{skipCloud:true})")
            page.locator("#cloud-account-banner button").tap()
            page.wait_for_function("CloudDB.accountId==='same-user' && !cloudSyncRunning")
            self.assertIn("users/same-user/quizlet_sets/audit_a", store)
            expect(page.locator("#cloud-account-banner")).to_contain_text("same-user@example.test")
            page.evaluate("onSetChange('audit_a')")
            page.wait_for_function("currentSet?.id==='audit_a'")
            page.evaluate("cloudLogout()")
            page.wait_for_function("!CloudDB.accountId && !cloudSyncRunning")
            self.assertIsNone(page.evaluate("currentSet"))
            self.assertFalse(page.evaluate("allDashboardSets.some(set=>set.id==='audit_a')"))
            page.evaluate("loadSetData('audit_a')")
            self.assertIsNone(page.evaluate("currentSet"))
            page.evaluate("changeCloudUser('other-user')")
            page.wait_for_function("CloudDB.accountId==='other-user' && !cloudSyncRunning")
            result = page.evaluate("""async()=>{
                const set=await Database.getSetById('audit_a');
                try{await saveCustomSet({...set,title:'Not mine'});return null}
                catch(error){return error.message}
            }""")
            self.assertIn("tài khoản khác", result)
            self.assertFalse(any(path.startswith("users/other-user/") for path in store))
        finally:
            context.close()

    def test_profile_avatar_tracks_google_auth_not_local_learner_name(self):
        context, page = self.cloud_device({}, uid=None)
        try:
            page.locator('#nav-user-avatar').click()
            expect(page.locator('#nav-user-avatar')).to_have_class('avatar-circle-modern signed-out')
            expect(page.locator('#nav-user-avatar-image')).to_be_hidden()
            expect(page.locator('#profile-menu-name-val')).to_have_text('Chưa đăng nhập')
            expect(page.locator('#profile-menu-device-val')).to_contain_text('Đặng Vũ')
            expect(page.locator('#profile-login-action')).to_be_visible()
            expect(page.locator('#profile-logout-action')).to_be_hidden()

            page.evaluate('CloudDB.signIn()')
            page.wait_for_function("CloudDB.accountId === 'same-user'")
            expect(page.locator('#profile-menu-name-val')).to_have_text('Google Same User')
            expect(page.locator('#profile-menu-device-val')).to_contain_text('same-user@example.test')
            expect(page.locator('#nav-user-avatar-image')).to_have_attribute(
                'src', 'https://images.example.test/same-user.png')
            expect(page.locator('#profile-login-action')).to_be_hidden()
            expect(page.locator('#profile-logout-action')).to_be_visible()
            page.locator('#nav-user-avatar-image').evaluate("image => image.dispatchEvent(new Event('error'))")
            expect(page.locator('#nav-user-avatar-image')).to_be_hidden()
            expect(page.locator('#nav-user-avatar .avatar-initials')).to_be_visible()
            page.evaluate('updateLearnerProfileUI()')
            expect(page.locator('#nav-user-avatar-image')).to_be_hidden()
            expect(page.locator('#nav-user-avatar .avatar-initials')).to_be_visible()

            page.evaluate('CloudDB.signOut()')
            page.wait_for_function('!CloudDB.accountId')
            expect(page.locator('#profile-menu-name-val')).to_have_text('Chưa đăng nhập')
            expect(page.locator('#nav-user-avatar-image')).to_be_hidden()
            expect(page.locator('#profile-login-action')).to_be_visible()
        finally:
            context.close()

    def test_cloud_login_reports_missing_firebase_configuration(self):
        context, page = self.cloud_device({}, uid=None, mobile=True)
        try:
            page.evaluate("window.mockLoginError='auth/configuration-not-found'")
            page.locator("#cloud-account-banner button").tap()
            expect(page.locator("#cloud-account-modal")).to_be_visible()
            expect(page.locator("#cloud-account-status")).to_contain_text("Firebase chưa bật Authentication")
        finally:
            context.close()

    def test_personal_cached_set_stays_available_when_sdk_is_offline(self):
        context, page = self.cloud_device({})
        try:
            page.evaluate("async fixture=>{await saveCustomSet(fixture);await loadSetsList(fixture.id)}", FIXTURE)
            context.unroute("https://**/*")
            context.route("https://**/*", lambda route: route.abort())
            page.reload()
            page.wait_for_function("window.appReady && currentSet?.id==='audit_a'")
            self.assertEqual(page.evaluate("currentSet.cloudAccount"), "same-user")
            self.assertEqual(page.evaluate("cardsState.length"), 5)
        finally:
            context.close()

    def test_newer_edit_is_preserved_during_cloud_acknowledgment(self):
        self.seed()
        self.page.evaluate("""async()=>{
            const update=Database.updateSet.bind(Database);
            let calls=0;
            Database.updateSet=async(id,fn)=>{
                if(++calls===2){
                    const current=await Database.getSetById(id);
                    await Database.saveSet({...current,title:'Edited before acknowledgment',localRevision:'newest',dirty:true});
                }
                return update(id,fn);
            };
            window.CloudDB={accountId:'test-user',getAllSets:async()=>[],saveSet:async set=>set.localRevision};
            await syncCloudSets();
        }""")
        saved = self.page.evaluate("Database.getSetById('audit_a')")
        self.assertEqual(saved['title'], 'Edited before acknowledgment')
        self.assertTrue(saved['dirty'])

    def test_failed_cloud_set_does_not_block_other_uploads(self):
        self.page.evaluate("""async fixture=>{
            await saveCustomSet({...fixture,id:'bad'});
            await saveCustomSet({...fixture,id:'good'});
            window.savedCloudIds=[];
            window.CloudDB={accountId:'test-user',getAllSets:async()=>[],saveSet:async set=>{
                if(set.id==='bad') throw new Error('One invalid record');
                savedCloudIds.push(set.id);return set.localRevision;
            }};
            await syncCloudSets();
        }""", FIXTURE)
        self.assertEqual(self.page.evaluate("savedCloudIds"), ["good"])
        self.assertTrue(self.page.evaluate("(async()=>(await Database.getSetById('bad')).dirty)()"))
        self.assertFalse(self.page.evaluate("(async()=>(await Database.getSetById('good')).dirty)()"))

    def test_reimport_deleted_set_restores_visibility(self):
        self.seed()
        self.page.evaluate("deleteSet('audit_a')")
        self.assertTrue(self.page.evaluate("s=>parseAndImportText(JSON.stringify(s))", FIXTURE))
        self.assertTrue(self.page.evaluate("allDashboardSets.some(s=>s.id==='audit_a')"))
        self.assertFalse(self.page.evaluate("getDeletedSetIds().includes('audit_a')"))
        self.assertEqual(self.page.evaluate("currentSet.id"), "audit_a")

    def test_cloud_failed_read_does_not_write(self):
        self.seed()
        self.page.evaluate("""async()=> {
            window.cloudWrites=[];
            window.CloudDB={accountId:'test-user',getAllSets:async()=>{throw new Error('offline')},
                saveSet:async(...args)=>cloudWrites.push(args)};
            await syncCloudSets();
        }""")
        self.assertEqual(self.page.evaluate("cloudWrites.length"), 0)
        self.assertTrue(self.page.evaluate("(async()=> (await Database.getSetById('audit_a')).dirty)()"))

    def test_cloud_new_version_refreshes_local_without_losing_progress(self):
        self.seed()
        self.page.evaluate("""async()=> {
            toggleStar('0');
            const set=await Database.getSetById('audit_a');
            await Database.saveSet({...set,dirty:false,cloudRevision:'r1'}, {preserveTimestamp:true});
            window.CloudDB={accountId:'test-user',getAllSets:async()=>[
                {...set,title:'Updated remotely',cloudRevision:'r2',cloudAccount:'test-user'}],
                saveSet:async()=>{throw new Error('Unexpected write')}};
            await syncCloudSets();
            await loadSetData('audit_a');
        }""")
        self.assertEqual(self.page.evaluate("currentSet.title"), "Updated remotely")
        self.assertTrue(self.page.evaluate("cardsState[0].starred"))

    def test_created_set_waits_for_authenticated_cloud_persistence(self):
        self.page.evaluate("""async()=>{
            window.cloudSaveCalls=[];
            window.CloudDB={accountId:'test-user',getAllSets:async()=>[],
                saveSet:async set=>{cloudSaveCalls.push(set.id);return set.localRevision}};
            await saveCustomSet({id:'cloud_created',title:'Cloud created',cards:[
                {id:'one',term:'hello',definition:'xin chào'}]});
        }""")
        self.assertEqual(self.page.evaluate("cloudSaveCalls"), ["cloud_created"])
        saved = self.page.evaluate("Database.getSetById('cloud_created')")
        self.assertFalse(saved["dirty"])
        self.assertEqual(saved["cloudAccount"], "test-user")
        self.assertEqual(saved["cloudRevision"], saved["localRevision"])

    def test_cloud_conflict_keeps_local_changes(self):
        self.seed()
        self.page.evaluate("""async()=> {
            const local=await Database.getSetById('audit_a');
            window.cloudWrites=[];
            window.CloudDB={accountId:'test-user',getAllSets:async()=>[
                {...local,title:'New remote',cloudRevision:'r2',cloudAccount:'test-user'}],
                saveSet:async(...args)=>cloudWrites.push(args)};
            await syncCloudSets();
        }""")
        self.assertEqual(self.page.evaluate("cloudWrites.length"), 0)
        self.assertEqual(self.page.evaluate("(async()=> (await Database.getSetById('audit_a')).title)()"), "Audit A")
        expect(self.page.locator("#cloud-status-text")).to_have_text("Có xung đột")

    def test_edits_during_upload_remain_dirty(self):
        self.seed()
        self.page.evaluate("""async()=> {
            window.uploadStarted=false;window.releaseUpload=null;
            window.CloudDB={accountId:'test-user',getAllSets:async()=>[],
                saveSet:async()=>{uploadStarted=true;return new Promise(resolve=>releaseUpload=resolve)}};
            window.runningSync=syncCloudSets();
        }""")
        self.page.wait_for_function("uploadStarted")
        self.page.evaluate("""async()=> {
            const local=await Database.getSetById('audit_a');
            await Database.saveSet({...local,title:'Edited during upload',localRevision:'new-edit',dirty:true});
            releaseUpload('committed-old-edit');
            await runningSync;
        }""")
        self.assertEqual(self.page.evaluate("(async()=> (await Database.getSetById('audit_a')).title)()"), "Edited during upload")
        self.assertTrue(self.page.evaluate("(async()=> (await Database.getSetById('audit_a')).dirty)()"))

    def test_invalid_legacy_record_does_not_break_library_and_can_be_repaired(self):
        self.page.evaluate("""async()=> {
            const db=await dbPromise;
            await new Promise((resolve,reject)=>{
                const tx=db.transaction('sets','readwrite');
                tx.objectStore('sets').put({id:'broken',title:'Old empty set',cards:[]});
                tx.oncomplete=resolve;tx.onerror=reject;
            });
        }""")
        self.page.reload()
        self.page.wait_for_function("window.appReady")
        expect(self.page.locator(".set-card-modern")).to_have_count(21)
        self.page.locator('[data-set-id="broken"] button', has_text="Sửa").click()
        expect(self.page.locator("#create-set-view")).to_be_visible()
        self.page.locator(".term-input").first.fill("fixed")
        self.page.locator(".def-input").first.fill("đã sửa")
        self.page.locator("#btn-save-set-top").click()
        self.page.wait_for_function("currentSet?.id==='broken' && cardsState.length===1")

    def test_missing_indexeddb_set_is_restored_from_same_origin_backup(self):
        self.seed()
        self.page.evaluate("""async()=>{
            await Database.deleteSet('audit_a');
            localStorage.setItem('qp_migrated_v2', 'true');
            await migrateLocalStorageToIndexedDB();
        }""")
        restored = self.page.evaluate("Database.getSetById('audit_a')")
        self.assertEqual(restored["title"], "Audit A")
        self.assertEqual(len(restored["cards"]), 5)

    def test_text_import_preserves_definition_and_rejects_bad_lines(self):
        self.assertFalse(self.page.evaluate("parseAndImportText('Ratio\\tx = 1: 2\\nBad line')"))
        self.assertIsNone(self.page.evaluate("currentSet"))
        self.assertTrue(self.page.evaluate("parseAndImportText('Ratio\\tx = 1: 2')"))
        self.assertEqual(self.page.evaluate("currentSet.cards[0].definition"), "x = 1: 2")

    def test_failed_set_load_disables_stale_actions(self):
        self.seed()
        self.page.evaluate("onSetChange('missing')")
        self.page.wait_for_selector("#app [role=alert]")
        self.assertIsNone(self.page.evaluate("currentSet"))
        expect(self.page.locator(".option-btn")).to_have_count(0)
        expect(self.page.locator("#btn-del-set")).to_be_disabled()
        expect(self.page.locator("#btn-edit-set")).to_be_disabled()

    def test_learn_and_test_resume(self):
        self.seed()
        self.page.evaluate("handleChoice(currentRoundOptions.indexOf(currentCorrectChoice))")
        self.page.wait_for_function("currentCardIndex===1")
        self.page.reload()
        self.page.wait_for_selector(".study-card")
        self.assertEqual(self.page.evaluate("currentCardIndex"), 1)
        self.assertEqual(self.page.evaluate("currentRoundQueue[currentCardIndex].id"), "1")
        self.page.evaluate("switchMode('test')")
        questions = self.page.evaluate("testState.questions")
        self.page.evaluate("testState.userAnswers[testState.questions[0].id]='draft answer'; saveActiveSession()")
        self.page.reload()
        self.page.wait_for_selector(".test-q-card")
        self.assertEqual(self.page.evaluate("testState.questions"), questions)
        self.assertEqual(self.page.evaluate("testState.userAnswers[1]"), "draft answer")

    def test_session_restore_deduplicates_old_retry_queue_and_keeps_active_card(self):
        self.seed()
        self.page.evaluate("""() => {
            const snapshot = SessionState.read();
            snapshot.queue = ['0', '1', '1', '1', '2', '3', '4'];
            snapshot.cardIndex = 3;
            snapshot.phase = 'question';
            snapshot.feedback = null;
            localStorage.setItem('qp_active_session', JSON.stringify(snapshot));
        }""")
        self.page.reload()
        self.page.wait_for_selector(".study-card")
        self.assertEqual(self.page.evaluate("currentRoundQueue.map(card => card.id)"), ["0", "1", "1", "2", "3", "4"])
        self.assertEqual(self.page.evaluate("currentCardIndex"), 2)

    def test_reset_keeps_stars_after_reload(self):
        self.seed()
        self.page.evaluate("toggleStar('0')")
        self.page.evaluate("resetSetProgress()")
        self.page.reload()
        self.page.wait_for_selector(".study-card")
        self.assertTrue(self.page.evaluate("cardsState[0].starred"))
        self.assertEqual(self.page.evaluate("cardsState[0].mastery"), 0)

    def test_override_and_feedback_resume(self):
        self.seed()
        self.page.evaluate("handleChoice(currentRoundOptions.findIndex(x=>x!==currentCorrectChoice))")
        self.page.wait_for_selector(".feedback-box")
        self.page.reload()
        self.page.wait_for_selector(".feedback-box")
        self.page.locator(".override-btn").click()
        self.assertEqual(self.page.evaluate("cardsState[0].mastery"), 1)

    def test_correct_answers_advance_promptly_and_finish_round(self):
        for mode in ("learn", "choice", "write"):
            with self.subTest(mode=mode):
                fixture = copy.deepcopy(FIXTURE)
                fixture["id"] = f"correct_{mode}"
                fixture["cards"] = fixture["cards"][:2]
                self.seed(fixture)
                self.page.evaluate("mode => switchMode(mode)", mode)

                for phase in (("choice", "write") if mode == "learn" else (mode,)):
                    for index in range(2):
                        if phase == "write":
                            answer = self.page.evaluate("currentCorrectChoice")
                            self.page.locator("#write-user-input").fill(answer)
                            self.page.locator(".btn-submit-write").click()
                        else:
                            answer_index = self.page.evaluate("currentRoundOptions.indexOf(currentCorrectChoice)")
                            self.page.locator(".option-btn").nth(answer_index).click()

                        if mode == "learn" and phase == "choice" and index == 1:
                            self.page.wait_for_selector("#write-user-input", timeout=2000)
                        else:
                            self.page.wait_for_function("index => currentCardIndex === index", arg=index + 1, timeout=2000)

                expect(self.page.locator(".summary-title")).to_have_text("Hoàn thành vòng học này!")
                self.assertEqual(self.page.evaluate("cardsState.map(card => card.mastery)"), [2, 2] if mode == "learn" else [1, 1])
                saved = self.page.evaluate("SessionState.read()")
                self.assertEqual(saved["cardIndex"], 2)
                self.assertEqual(saved["phase"], "summary")

    def test_wrong_answers_do_not_expand_a_fixed_round(self):
        fixture = copy.deepcopy(FIXTURE)
        fixture["id"] = "fixed_round"
        fixture["cards"] = [
            {"id": str(i), "term": f"word{i}", "definition": f"meaning{i}", "image": ""}
            for i in range(40)
        ]
        self.seed(fixture)
        self.page.evaluate("""() => {
            settings.roundSize = 10;
            settings.learnQuestionType = 'choice_only';
            startModeView();
        }""")
        self.assertEqual(self.page.evaluate("currentRoundQueue.length"), 10)

        wrong_index = self.page.evaluate("currentRoundOptions.findIndex(value => value !== currentCorrectChoice)")
        self.page.evaluate("index => handleChoice(index)", wrong_index)
        self.page.wait_for_selector(".feedback-box")
        self.assertEqual(self.page.evaluate("currentRoundQueue.length"), 10)
        self.page.locator("#btn-next-wrong").click()

        for index in range(1, 10):
            correct_index = self.page.evaluate("currentRoundOptions.indexOf(currentCorrectChoice)")
            self.page.evaluate("answer => handleChoice(answer)", correct_index)
            self.page.wait_for_function("index => currentCardIndex === index", arg=index + 1, timeout=2000)

        expect(self.page.locator(".summary-title")).to_have_text("Hoàn thành vòng học này!")
        self.assertEqual(self.page.evaluate("currentRoundQueue.length"), 10)

    def test_learn_cycles_ten_choices_then_ten_written_answers_for_the_same_cards(self):
        fixture = copy.deepcopy(FIXTURE)
        fixture["id"] = "rotating_groups"
        fixture["cards"] = [
            {"id": str(i), "term": f"word{i}", "definition": f"meaning{i}", "image": ""}
            for i in range(62)
        ]
        self.seed(fixture)
        self.page.evaluate("toggleSettingsModal()")
        self.page.locator("#opt-round-size").select_option("10")
        self.page.locator("#opt-learn-question-type").select_option("both")
        self.page.locator("#settings-modal button", has_text="Lưu & Tiếp tục học").click()
        self.page.clock.install()
        for start in range(0, 62, 10):
            ids = [str(i) for i in range(start, min(start + 10, 62))]
            self.assertEqual(self.page.evaluate("currentRoundQueue.map(card => card.id)"), ids)
            for _ in ids:
                expect(self.page.locator(".option-btn").first).to_be_visible()
                self.page.evaluate("handleChoice(currentRoundOptions.indexOf(currentCorrectChoice))")
                self.page.clock.run_for(800)
            expect(self.page.locator("#write-user-input")).to_be_visible()
            self.assertEqual(self.page.evaluate("currentCardIndex"), 0)
            self.assertEqual(self.page.evaluate("currentRoundQueue.map(card => card.id)"), ids)
            expect(self.page.locator("#stat-learning")).to_have_text(str(len(ids)))
            for card_id in ids:
                self.assertEqual(self.page.evaluate("currentRoundQueue[currentCardIndex].id"), card_id)
                answer = self.page.evaluate("currentCorrectChoice")
                self.page.locator("#write-user-input").fill(answer)
                self.page.locator(".btn-submit-write").click()
                self.page.clock.run_for(800)
            expect(self.page.locator(".summary-title")).to_have_text("Hoàn thành vòng học này!")
            expect(self.page.locator("#stat-mastered")).to_have_text(str(start + len(ids)))
            if start + len(ids) < 62:
                self.page.locator("#app .btn-continue").click()

    def test_learn_written_phase_and_feedback_resume_without_adding_new_cards(self):
        self.seed()
        self.page.evaluate("startModeView()")
        self.page.clock.install()
        for _ in range(5):
            self.page.evaluate("handleChoice(currentRoundOptions.indexOf(currentCorrectChoice))")
            self.page.clock.run_for(800)
        expect(self.page.locator("#write-user-input")).to_be_visible()
        self.page.locator("#write-user-input").fill("unfinished answer")
        self.page.reload()
        self.page.wait_for_function("window.appReady && document.getElementById('write-user-input')")
        expect(self.page.locator("#write-user-input")).to_have_value("unfinished answer")
        self.assertEqual(self.page.evaluate("currentCardIndex"), 0)
        self.page.locator("#write-user-input").fill("wrong")
        self.page.locator(".btn-submit-write").click()
        self.page.clock.run_for(800)
        expect(self.page.locator(".feedback-box")).to_be_visible()
        self.page.reload()
        self.page.wait_for_selector(".feedback-box")
        self.page.locator("#btn-next-wrong").click()
        expect(self.page.locator("#write-user-input")).to_be_visible()
        self.assertEqual(self.page.evaluate("currentCardIndex"), 1)
        self.assertEqual(self.page.evaluate("currentRoundQueue.map(card => card.id)"), [str(i) for i in range(5)])

    def test_learn_checks_previously_learned_cards_before_opening_a_new_group(self):
        fixture = copy.deepcopy(FIXTURE)
        fixture["id"] = "pending_written"
        fixture["cards"] = [
            {"id": str(i), "term": f"word{i}", "definition": f"meaning{i}", "image": ""}
            for i in range(62)
        ]
        self.seed(fixture)
        self.page.evaluate("""() => {
            cardsState.slice(0, 13).forEach(card => Object.assign(card, {
                mastery: 1, nextReview: Date.now() + 300000
            }));
            saveProgressToStorage();
            settings.roundSize = 10;
            settings.learnQuestionType = 'both';
            startModeView();
        }""")
        expect(self.page.locator("#write-user-input")).to_be_visible()
        self.assertEqual(self.page.evaluate("currentRoundQueue.map(card => card.id)"), [str(i) for i in range(10)])

    def test_learn_group_size_follows_every_user_selection(self):
        self.page.clock.install()
        for count in (5, 7, 10, 15, 999):
            with self.subTest(count=count):
                fixture = copy.deepcopy(FIXTURE)
                fixture["id"] = f"group_size_{count}"
                fixture["cards"] = [
                    {"id": str(i), "term": f"word{i}", "definition": f"meaning{i}", "image": ""}
                    for i in range(17)
                ]
                self.seed(fixture)
                self.page.evaluate("toggleSettingsModal()")
                self.page.locator("#opt-round-size").select_option(str(count))
                self.page.locator("#opt-learn-question-type").select_option("both")
                self.page.locator("#settings-modal button", has_text="Lưu & Tiếp tục học").click()
                size = min(count, 17)
                ids = [str(i) for i in range(size)]
                self.assertEqual(self.page.evaluate("currentRoundQueue.map(card => card.id)"), ids)
                for _ in range(size):
                    self.page.evaluate("handleChoice(currentRoundOptions.indexOf(currentCorrectChoice))")
                    self.page.clock.run_for(800)
                expect(self.page.locator("#write-user-input")).to_be_visible()
                self.assertEqual(self.page.evaluate("currentRoundQueue.map(card => card.id)"), ids)
                expect(self.page.locator(".card-step-tag")).to_have_text(f"Kiểm tra viết 1 / {size}")

    def test_shuffle_setting_keeps_the_same_group_and_restores_its_order(self):
        self.seed()
        self.page.evaluate("StudyUtils.shuffle = values => [...values].reverse(); toggleSettingsModal()")
        self.page.locator("#opt-round-size").select_option("5")
        self.page.locator("#opt-shuffle-questions").check()
        self.page.locator("#settings-modal button", has_text="Lưu & Tiếp tục học").click()
        self.assertEqual(self.page.evaluate("currentRoundQueue.map(card => card.id)"), ["4", "3", "2", "1", "0"])
        self.page.clock.install()
        for _ in range(5):
            self.page.evaluate("handleChoice(currentRoundOptions.indexOf(currentCorrectChoice))")
            self.page.clock.run_for(800)
        expect(self.page.locator("#write-user-input")).to_be_visible()
        self.assertEqual(self.page.evaluate("currentRoundQueue.map(card => card.id)"), ["0", "1", "2", "3", "4"])
        self.page.locator("#write-user-input").fill("saved draft")
        self.page.reload()
        self.page.wait_for_function("window.appReady && document.getElementById('write-user-input')")
        self.assertEqual(self.page.evaluate("currentRoundQueue.map(card => card.id)"), ["0", "1", "2", "3", "4"])
        expect(self.page.locator("#write-user-input")).to_have_value("saved draft")
        self.page.evaluate("toggleSettingsModal()")
        expect(self.page.locator("#opt-shuffle-questions")).to_be_checked()
        expect(self.page.locator("#opt-round-size")).to_have_value("5")

    def test_shuffle_setting_applies_to_question_modes_and_can_be_disabled(self):
        self.seed()
        self.page.evaluate("StudyUtils.shuffle = values => [...values].reverse()")
        for mode in ("learn", "choice", "write", "test"):
            for shuffled in (True, False):
                with self.subTest(mode=mode, shuffled=shuffled):
                    self.page.evaluate("""args => {
                        settings.shuffleQuestions = args.shuffled;
                        currentMode = args.mode;
                        startModeView();
                    }""", {"mode": mode, "shuffled": shuffled})
                    actual = self.page.evaluate("testState.questions.map(q => q.cardId)" if mode == "test"
                                                else "currentRoundQueue.map(card => card.id)")
                    self.assertEqual(actual, ["4", "3", "2", "1", "0"] if shuffled else ["0", "1", "2", "3", "4"])

    def test_legacy_completed_learning_group_opens_its_written_phase(self):
        self.seed()
        self.page.evaluate("""() => {
            cardsState.forEach(card => Object.assign(card, {mastery: 1, nextReview: Date.now() + 300000}));
            saveProgressToStorage();
            const snapshot = SessionState.read();
            delete snapshot.learnPhase;
            const savedSettings = JSON.parse(snapshot.settings);
            delete savedSettings.shuffleQuestions;
            snapshot.settings = JSON.stringify(savedSettings);
            snapshot.cardIndex = snapshot.queue.length;
            snapshot.phase = 'summary';
            localStorage.setItem('qp_active_session', JSON.stringify(snapshot));
        }""")
        self.page.reload()
        self.page.wait_for_selector("#write-user-input")
        self.assertEqual(self.page.evaluate("currentCardIndex"), 0)
        self.assertEqual(self.page.evaluate("currentRoundQueue.map(card => card.id)"), [str(i) for i in range(5)])

    def test_test_mode_uses_question_limit_and_answer_direction(self):
        fixture = copy.deepcopy(FIXTURE)
        fixture["id"] = "limited_test"
        fixture["cards"] = [
            {"id": str(i), "term": f"word{i}", "definition": f"meaning{i}", "image": ""}
            for i in range(40)
        ]
        self.seed(fixture)
        self.page.evaluate("settings.roundSize = 10; settings.answerWith = 'term'; switchMode('test')")
        self.assertEqual(self.page.evaluate("testState.questions.length"), 10)
        self.assertTrue(self.page.evaluate("testState.questions.every(q => q.prompt.startsWith('meaning'))"))
        for question in self.page.evaluate("testState.questions"):
            if question["type"] == "written":
                self.assertTrue(question["correct"].startswith("word"))
            elif question["type"] == "choice":
                self.assertTrue(question["correct"].startswith("word"))
                self.assertIn(question["correct"], question["options"])
            else:
                self.assertTrue(question["actualDef"].startswith("word"))

    def test_correct_answer_survives_progress_and_session_save_failures(self):
        self.seed()
        self.page.evaluate("""() => {
            Database.saveProgress = () => { throw new Error('Storage unavailable'); };
            SessionState.save = () => { throw new Error('Snapshot unavailable'); };
        }""")
        answer_index = self.page.evaluate("currentRoundOptions.indexOf(currentCorrectChoice)")
        self.page.locator(".option-btn").nth(answer_index).click()
        self.page.wait_for_function("currentCardIndex === 1", timeout=2000)
        self.assertEqual(self.page.evaluate("cardsState[0].mastery"), 1)
        self.assertEqual(self.page.evaluate("JSON.parse(localStorage.getItem(getStorageKey(currentSet.id)))['0'].box"), 2)

    def test_pending_progress_write_and_storage_quota_do_not_delay_advancement(self):
        self.seed()
        self.page.evaluate("""() => {
            Database.saveProgress = () => new Promise(() => {});
            const original = Storage.prototype.setItem;
            Storage.prototype.setItem = function(key, value) {
                if (key.startsWith('qp_progress_') || key === 'qp_active_session') {
                    throw new DOMException('Storage full', 'QuotaExceededError');
                }
                return original.call(this, key, value);
            };
        }""")
        index = self.page.evaluate("currentRoundOptions.indexOf(currentCorrectChoice)")
        self.page.locator(".option-btn").nth(index).click()
        self.page.wait_for_function("currentCardIndex === 1", timeout=2000)

    def test_retype_input_waits_for_ime_composition_to_finish(self):
        self.seed()
        self.page.evaluate("switchMode('write')")
        self.page.locator('#write-user-input').fill('wrong')
        self.page.locator('.btn-submit-write').click()
        self.page.wait_for_selector('#retype-input')
        self.page.wait_for_function("document.activeElement.id === 'retype-input'")
        self.page.evaluate("""() => {
            const input = document.getElementById('retype-input');
            input.value = currentCorrectChoice;
            input.dispatchEvent(new InputEvent('input', {bubbles:true, isComposing:true}));
        }""")
        expect(self.page.locator('#retype-input')).to_be_enabled()
        self.page.evaluate("document.getElementById('retype-input').dispatchEvent(new InputEvent('input', {bubbles:true}))")
        self.page.wait_for_function("currentCardIndex === 1", timeout=2000)

    def test_suspended_answer_timer_resumes_once_when_page_returns(self):
        self.page.clock.install()
        self.page.clock.pause_at(self.page.evaluate("Date.now() / 1000") + 1)
        for event in ("visibilitychange", "pageshow"):
            with self.subTest(event=event):
                fixture = copy.deepcopy(FIXTURE)
                fixture["id"] = f"resume_{event}"
                self.seed(fixture)
                self.page.evaluate("handleChoice(currentRoundOptions.indexOf(currentCorrectChoice))")
                self.page.clock.set_system_time(self.page.evaluate("Date.now() / 1000") + 1)
                self.page.evaluate("""event => {
                    if (event === 'pageshow') window.dispatchEvent(new PageTransitionEvent(event, {persisted:true}));
                    else document.dispatchEvent(new Event(event));
                }""", event)
                self.assertEqual(self.page.evaluate("currentCardIndex"), 1)
                self.page.clock.run_for(1000)
                self.assertEqual(self.page.evaluate("currentCardIndex"), 1)

    def test_reloading_during_written_advance_does_not_reuse_previous_answer(self):
        self.seed()
        self.page.evaluate("switchMode('write')")
        self.page.evaluate("""() => {
            document.getElementById('write-user-input').value = currentCorrectChoice;
            handleWriteSubmit();
        }""")
        self.page.reload()
        self.page.wait_for_function("window.appReady && currentCardIndex === 1")
        expect(self.page.locator("#write-user-input")).to_have_value("")

    def test_reselecting_active_mode_does_not_cancel_answer_transition(self):
        self.seed()
        self.page.evaluate("switchMode('choice')")
        self.page.evaluate("handleChoice(currentRoundOptions.indexOf(currentCorrectChoice)); switchMode('choice')")
        self.page.wait_for_function("currentCardIndex === 1", timeout=2000)
        self.assertEqual(self.page.evaluate("cardsState[0].mastery"), 1)

    def test_manual_feedback_continue_advances_once(self):
        self.seed()
        self.page.clock.install()
        self.page.evaluate("handleChoice(currentRoundOptions.findIndex(value => value !== currentCorrectChoice))")
        self.page.clock.fast_forward(1200)
        self.page.locator("#btn-next-wrong").click()
        self.assertEqual(self.page.evaluate("currentCardIndex"), 1)
        self.page.clock.fast_forward(4000)
        self.assertEqual(self.page.evaluate("currentCardIndex"), 1)

    def test_mobile_tap_and_repeated_submission_advance_only_once(self):
        context = self.browser.new_context(is_mobile=True, has_touch=True, viewport={"width":390,"height":844})
        try:
            context.route("https://**/*", lambda route: route.abort())
            page = context.new_page()
            page.on("pageerror", lambda error: self.errors.append(str(error)))
            page.add_init_script("localStorage.setItem('qp_settings',JSON.stringify({autoSound:false}));")
            page.goto(self.url)
            page.wait_for_function("window.appReady")
            page.evaluate("async fixture => { await saveCustomSet(fixture); await loadSetsList(fixture.id); }", FIXTURE)
            index = page.evaluate("currentRoundOptions.indexOf(currentCorrectChoice)")
            page.locator(".option-btn").nth(index).tap()
            page.evaluate("handleChoice(currentRoundOptions.indexOf(currentCorrectChoice))")
            page.wait_for_function("currentCardIndex === 1", timeout=2000)
            self.assertEqual(page.evaluate("cardsState.map(card => card.mastery)"), [1, 0, 0, 0, 0])
            page.locator("#mob-nav-study").tap()
            self.assertEqual(page.evaluate("currentCardIndex"), 1)
        finally:
            context.close()

    def test_wrong_answer_feedback_waits_for_manual_continue(self):
        self.seed()
        self.page.clock.install()
        self.page.evaluate("handleChoice(currentRoundOptions.findIndex(x=>x!==currentCorrectChoice))")
        self.page.clock.fast_forward(1200)
        expect(self.page.locator(".feedback-box")).to_be_visible()
        self.page.clock.fast_forward(10000)
        self.assertEqual(self.page.evaluate("currentCardIndex"), 0)
        self.page.locator("#btn-next-wrong").click()
        self.assertEqual(self.page.evaluate("currentCardIndex"), 1)

        self.page.locator("#mode-write").click()
        self.page.locator("#write-user-input").fill("not the answer")
        self.page.locator(".btn-submit-write").click()
        self.page.clock.fast_forward(700)
        expect(self.page.locator("#retype-input")).to_be_visible()
        self.page.locator("#retype-input").fill("still wrong")
        self.page.keyboard.press("Enter")
        self.page.clock.fast_forward(10000)
        self.assertEqual(self.page.evaluate("currentCardIndex"), 0)
        self.page.locator("#btn-next-wrong").click()
        self.assertEqual(self.page.evaluate("currentCardIndex"), 1)

    def test_test_mode_moves_to_next_question_and_focuses_written_input(self):
        self.seed()
        self.page.evaluate("switchMode('test')")
        self.page.evaluate("""() => {
            testState = {isSubmitted:false,userAnswers:{},questions:[
                {id:1,cardId:'0',type:'choice',prompt:'one',correct:'first',options:['first','other'],image:''},
                {id:2,cardId:'1',type:'choice',prompt:'two',correct:'second',options:['second','other'],image:''},
                {id:3,cardId:'2',type:'written',prompt:'three',correct:'third',image:''}
            ]};
            renderTestQuestions();
        }""")
        self.page.evaluate("selectTestOption(1, 0)")
        self.page.wait_for_function("scrollY > 0")
        self.assertTrue(self.page.evaluate("document.getElementById('test_q_2').getBoundingClientRect().top < innerHeight"))
        self.page.evaluate("selectTestOption(2, 0)")
        self.page.wait_for_function("document.activeElement.matches('.test-written-input')")

    def test_partial_cards_rejected_on_import_but_legacy_can_be_viewed(self):
        partial = {"id":"partial","title":"Partial","cards":[{"id":"p","term":"question","definition":""}]}
        self.assertFalse(self.page.evaluate("s=>parseAndImportText(JSON.stringify(s))", partial))
        self.page.evaluate("async s=>{await Database.saveSet(s);await loadSetsList(s.id);}", partial)
        expect(self.page.locator("#write-user-input")).to_have_count(0)
        self.page.evaluate("switchMode('flashcards')")
        expect(self.page.locator(".fc-container")).to_be_visible()
        self.page.evaluate("switchMode('write')")
        expect(self.page.locator("#write-user-input")).to_have_count(0)

    def test_mobile_controls_visible_and_modal_focus_trapped(self):
        self.seed()
        self.page.set_viewport_size({"width":390,"height":844})
        for id in ["btn-edit-set","btn-reset-prog","btn-export-set","btn-del-set"]:
            box=self.page.locator("#"+id).bounding_box()
            self.assertLessEqual(box["x"]+box["width"],390,id)
        self.page.locator(".mob-nav-create").click()
        self.page.locator("#import-tab-paste").click()
        self.page.locator("#import-pane-paste .btn-primary").focus()
        self.page.keyboard.press("Tab")
        self.assertTrue(self.page.evaluate("!!document.activeElement.closest('#quick-import-modal')"))
        self.page.keyboard.press("Escape")
        expect(self.page.locator("#quick-import-modal")).to_be_hidden()
        self.assertTrue(self.page.evaluate("document.activeElement.matches('.mob-nav-create')"))
        self.assertFalse(self.page.evaluate("document.getElementById('study-view').inert"))

    def test_bookmarklets_and_cloud_help_work_without_sdk(self):
        errors=self.page.evaluate("""()=>[...document.querySelectorAll('a[href^="javascript:"]')].map(a=>{
            try{new Function(a.getAttribute('href').slice(11));return null}catch(e){return e.message}
        })""")
        self.assertEqual(errors,[None,None])
        self.page.evaluate("showCloudStatusHelp()")
        expect(self.page.locator("#cloud-account-modal")).to_be_visible()
        expect(self.page.locator("#cloud-status-text")).to_have_text("Lưu trên máy")

    def test_compound_progress_keys_do_not_collide(self):
        self.page.evaluate("""async()=>{
            await Database.setCardBox('a_b','c',3,true);
            await Database.setCardBox('a','b_c',1,false);
        }""")
        self.assertEqual(self.page.evaluate("(async()=> (await Database.getProgress('a_b'))[0].box)()"),3)
        self.assertEqual(self.page.evaluate("(async()=> (await Database.getProgress('a'))[0].box)()"),1)

    def test_draft_and_json_file_import(self):
        self.page.evaluate("showCreateSetView()")
        self.page.locator("#create-title").fill("Unfinished draft")
        self.page.locator(".term-input").first.fill("draft term")
        self.page.reload()
        self.page.wait_for_function("window.appReady")
        expect(self.page.locator("#create-set-view")).to_be_visible()
        expect(self.page.locator("#create-title")).to_have_value("Unfinished draft")
        expect(self.page.locator(".term-input").first).to_have_value("draft term")
        self.page.evaluate("showDashboard();openQuickImportModal('paste')")
        self.page.locator("#import-json-file").set_input_files({
            "name":"set.json","mimeType":"application/json","buffer":json.dumps(FIXTURE).encode()})
        self.page.wait_for_function("currentSet?.id==='audit_a'")
        self.assertEqual(self.page.evaluate("cardsState.length"),5)

    def test_create_editor_fields_are_clear_on_desktop_and_mobile(self):
        self.page.evaluate("showCreateSetView()")
        for width, expected_columns in [(1280, 2), (390, 1)]:
            self.page.set_viewport_size({"width": width, "height": 900})
            layout = self.page.evaluate("""() => {
                const row = document.querySelector('#create-cards-list .card-row');
                const fields = [...row.querySelectorAll('.card-row-input')];
                return {
                    columns: getComputedStyle(row.querySelector('.card-row-inputs')).gridTemplateColumns.split(' ').length,
                    fields: fields.map(field => {
                        const label = row.querySelector(`label[for="${field.id}"]`);
                        const labelBox = label.getBoundingClientRect();
                        const fieldBox = field.getBoundingClientRect();
                        return {
                            placeholder: field.placeholder,
                            height: fieldBox.height,
                            right: fieldBox.right,
                            labelBottom: labelBox.bottom,
                            fieldTop: fieldBox.top
                        };
                    })
                };
            }""")
            self.assertEqual(layout["columns"], expected_columns)
            self.assertEqual([field["placeholder"] for field in layout["fields"]],
                             ["Nhập thuật ngữ...", "Nhập định nghĩa..."])
            for field in layout["fields"]:
                self.assertGreaterEqual(field["height"], 72)
                self.assertLessEqual(field["right"], width)
                self.assertLessEqual(field["labelBottom"], field["fieldTop"])

    def test_saved_set_opens_even_if_localstorage_backup_is_full(self):
        self.page.evaluate("""() => {
            const original = Storage.prototype.setItem;
            Storage.prototype.setItem = function(key, value) {
                if (key === 'qp_deleted_set_ids') throw new DOMException('Storage full', 'QuotaExceededError');
                return original.call(this, key, value);
            };
            showCreateSetView();
        }""")
        self.page.locator("#create-title").fill("Stored in IndexedDB")
        self.page.locator(".term-input").first.fill("term")
        self.page.locator(".def-input").first.fill("definition")
        self.page.locator("#btn-save-set-top").click()
        self.page.wait_for_function("currentSet?.title === 'Stored in IndexedDB'")
        self.assertEqual(self.page.evaluate("currentSet.cards.length"), 1)
        self.assertTrue(self.page.evaluate("document.getElementById('study-view').style.display !== 'none'"))

    def test_set_save_does_not_wait_for_slow_cloud_sync(self):
        self.page.evaluate("() => { window.syncCloudSets = () => new Promise(() => {}); }")
        self.page.evaluate("showCreateSetView()")
        self.page.locator("#create-title").fill("Save without network")
        self.page.locator(".term-input").first.fill("term")
        self.page.locator(".def-input").first.fill("definition")
        self.page.locator("#btn-save-set-top").click()
        self.page.wait_for_function("currentSet?.title === 'Save without network'")

    def test_srs_uses_due_dates(self):
        self.seed()
        self.page.evaluate("""()=>{
            cardsState.forEach(c=>{c.mastery=2;c.interval=1;c.nextReview=Date.now()+86400000});
            cardsState[2].nextReview=Date.now()-1000;
            prepareNextRound();
        }""")
        self.assertEqual(self.page.evaluate("currentRoundQueue.map(c=>c.id)"),["2"])
        self.page.evaluate("handleChoice(currentRoundOptions.indexOf(currentCorrectChoice))")
        self.page.wait_for_selector("#write-user-input")
        self.assertEqual(self.page.evaluate("cardsState[2].interval"),1)
        self.page.locator("#write-user-input").fill(self.page.evaluate("currentCorrectChoice"))
        self.page.locator(".btn-submit-write").click()
        self.page.wait_for_function("currentCardIndex===1")
        self.assertEqual(self.page.evaluate("cardsState[2].interval"),2)
        self.page.evaluate("prepareNextRound()")
        expect(self.page.locator("#app")).to_contain_text("Đã xong các thẻ đến hạn")

    def test_version_one_database_migrates_progress_without_data_loss(self):
        context = self.browser.new_context(service_workers="block")
        try:
            context.route("https://**/*", lambda route: route.abort())
            context.route("**/seed-v1", lambda route: route.fulfill(content_type="text/html", body="<html><body>seed</body></html>"))
            page = context.new_page()
            page.goto(self.url + "/seed-v1")
            page.evaluate("""async()=> {
                await new Promise((resolve,reject)=>{
                    const request=indexedDB.open('QuizletProDB',1);
                    request.onupgradeneeded=()=>{
                        const db=request.result;
                        db.createObjectStore('sets',{keyPath:'id'});
                        db.createObjectStore('progress',{keyPath:'id'}).createIndex('setId','setId');
                    };
                    request.onsuccess=()=>{
                        const db=request.result, tx=db.transaction(['sets','progress'],'readwrite');
                        tx.objectStore('sets').put({id:42,title:'Old numeric ID',cards:[{id:0,term:'old',definition:'cũ'}]});
                        tx.objectStore('progress').put({id:'42_0',setId:42,cardId:0,box:3,isStarred:true,nextReview:123});
                        tx.oncomplete=()=>{db.close();resolve()};
                        tx.onerror=reject;
                    };
                    request.onerror=reject;
                });
            }""")
            page.goto(self.url)
            page.wait_for_function("window.appReady")
            result = page.evaluate("async()=>({set:await Database.getSetById('42'),progress:await Database.getProgress('42')})")
            self.assertEqual(result["set"]["title"], "Old numeric ID")
            self.assertEqual(len(result["progress"]), 1)
            self.assertEqual(result["progress"][0]["box"], 3)
            self.assertTrue(result["progress"][0]["isStarred"])
            self.assertEqual(result["progress"][0]["id"], '["42","0"]')
        finally:
            context.close()

    def test_service_worker_reloads_application_and_sample_set_offline(self):
        context = self.browser.new_context()
        try:
            context.route("https://**/*", lambda route: route.abort())
            page = context.new_page()
            page.add_init_script("localStorage.setItem('qp_settings',JSON.stringify({autoSound:false}));")
            page.goto(self.url)
            page.wait_for_function("window.appReady")
            page.evaluate("navigator.serviceWorker.ready")
            page.wait_for_function("!!navigator.serviceWorker.controller")
            page.evaluate("onSetChange('927731678')")
            page.wait_for_function("currentSet?.id==='927731678'")
            context.set_offline(True)
            page.reload()
            page.wait_for_function("window.appReady && currentSet?.id==='927731678'")
            self.assertEqual(page.evaluate("cardsState.length"), 60)
            expect(page.locator(".study-card")).to_be_visible()
        finally:
            context.close()

    def test_firebase_adapter_compare_and_swap_and_idempotent_retry(self):
        context = self.browser.new_context(service_workers="block")
        try:
            def sdk(route):
                url = route.request.url
                if url.endswith("firebase-app.js"):
                    code = "export const initializeApp=()=>({});"
                elif url.endswith("firebase-auth.js"):
                    code = """const auth={currentUser:{uid:'test-user'}};
                        export const getAuth=()=>auth;
                        export const onAuthStateChanged=(a,cb)=>cb(a.currentUser);
                        export class GoogleAuthProvider {}
                        export const signInWithPopup=async()=>({});
                        export const signOut=async()=>{};"""
                elif url.endswith("firebase-firestore.js"):
                    code = """window.fakeCloud={};window.fakeWrites=0;
                        export const getFirestore=()=>({});
                        export const collection=(db,...parts)=>parts.join('/');
                        export const doc=(db,...parts)=>parts.join('/');
                        export const getDocsFromServer=async()=>({docs:[]});
                        export const onSnapshot=()=>()=>{};
                        export const runTransaction=async(db,fn)=>fn({
                            get:async ref=>({exists:()=>!!fakeCloud[ref],data:()=>fakeCloud[ref]}),
                            set:(ref,data)=>{fakeCloud[ref]=data;fakeWrites++}
                        });"""
                else:
                    route.abort()
                    return
                route.fulfill(content_type="application/javascript", headers={"Access-Control-Allow-Origin":"*"}, body=code)
            context.route("https://**/*", sdk)
            page = context.new_page()
            page.goto(self.url)
            page.wait_for_function("window.appReady && window.CloudDB?.accountId==='test-user'")
            result = page.evaluate("""async fixture=>{
                const path='users/test-user/quizlet_sets/'+fixture.id;
                fakeCloud[path]={...fixture,revision:'r2'};
                let conflict;
                try{await CloudDB.saveSet({...fixture,localRevision:'r3'},'r1')}
                catch(error){conflict=error.code}
                const writesAfterConflict=fakeWrites;
                const revision=await CloudDB.saveSet({...fixture,localRevision:'r3'},'r2');
                const retry=await CloudDB.saveSet({...fixture,localRevision:'r3'},'r2');
                return {conflict,writesAfterConflict,revision,retry,writes:fakeWrites};
            }""", FIXTURE)
            self.assertEqual(result, {"conflict":"conflict","writesAfterConflict":0,
                                      "revision":"r3","retry":"r3","writes":1})
        finally:
            context.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
