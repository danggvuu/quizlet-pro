/* Local-first cloud synchronization. SDK failure never removes the local UI. */
function getLocalAccountId() {
    if (window.CloudDB && window.CloudDB.accountReady !== false) return CloudDB.accountId || null;
    try { return localStorage.getItem('qp_cloud_account') || null; }
    catch { return null; }
}

function cloudErrorMessage(error) {
    if (error.code === 'auth/configuration-not-found') {
        return 'Firebase chưa bật Authentication. Mở Firebase Console, chọn Authentication và bật đăng nhập Google.';
    }
    if (error.code === 'auth/unauthorized-domain') {
        return `Thêm ${location.hostname} vào Authentication > Settings > Authorized domains trong Firebase Console.`;
    }
    if (error.code === 'auth/operation-not-allowed') {
        return 'Bật Google trong Authentication > Sign-in method của Firebase Console.';
    }
    if (error.code === 'permission-denied') {
        return 'Chưa có quyền truy cập thư viện cá nhân. Hãy triển khai firestore.rules cho đúng Firebase project.';
    }
    return error.message || 'Chưa kết nối được database. Nội dung trên máy vẫn được giữ lại.';
}

function renderCloudAccountBanner() {
    const dashboard = document.getElementById('dashboard-view');
    if (!dashboard) return;
    let banner = document.getElementById('cloud-account-banner');
    if (!banner) {
        banner = document.createElement('div');
        banner.id = 'cloud-account-banner';
        banner.className = 'dash-welcome-banner';
        banner.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:20px';
        const text = document.createElement('div');
        text.style.cssText = 'flex:1;min-width:180px;overflow-wrap:anywhere';
        const title = document.createElement('strong');
        title.className = 'cloud-account-title';
        const description = document.createElement('p');
        description.className = 'cloud-account-description';
        description.style.cssText = 'margin:6px 0 0;color:var(--text-muted);font-size:14px';
        text.append(title, description);
        const button = document.createElement('button');
        button.className = 'btn-primary';
        button.style.cssText = 'width:auto;flex-shrink:0';
        banner.append(text, button);
    }
    dashboard.prepend(banner);
    const client = window.CloudDB;
    banner.querySelector('.cloud-account-title').textContent = client?.accountId
        ? `Thư viện của ${client.accountEmail || 'bạn'}` : 'Mở học phần trên cả máy tính và điện thoại';
    banner.querySelector('.cloud-account-description').textContent = window.cloudSyncState?.message || (client?.accountId
        ? 'Đăng nhập cùng tài khoản Google trên thiết bị khác để mở các học phần đã đồng bộ.'
        : 'Đăng nhập cùng một tài khoản Google trên hai thiết bị. Khi chưa đăng nhập, học phần chỉ lưu trên máy này.');
    const button = banner.querySelector('button');
    button.textContent = client?.accountId ? 'Tài khoản và đồng bộ' : 'Đăng nhập Google';
    button.onclick = client && !client.accountId ? cloudLogin : showCloudStatusHelp;
}

function updateCloudSyncUI(status, message = '') {
    window.cloudSyncState = { status, message };
    const badge = document.getElementById('cloud-status-badge');
    if (!badge) return;
    const labels = { connected: 'Đã đồng bộ', syncing: 'Đang đồng bộ', conflict: 'Có xung đột',
        offline: 'Lưu trên máy', locked: 'Chưa có quyền', catalog: 'Lưu trên máy' };
    badge.className = `cloud-status-pill ${status === 'connected' ? 'online' : 'offline'}`;
    document.getElementById('cloud-status-text').textContent = labels[status] || labels.offline;
    badge.title = message || (status === 'catalog'
        ? 'Chưa đăng nhập Google. Bộ thẻ mới chỉ được lưu trên trình duyệt này.'
        : labels[status] || labels.offline);
    const info = document.getElementById('cloud-account-status');
    if (info) info.textContent = badge.title;
    renderCloudAccountBanner();
}

function showCloudStatusHelp() {
    const modal = document.getElementById('cloud-account-modal');
    const signedIn = !!window.CloudDB?.accountId;
    document.getElementById('cloud-account-info').textContent = signedIn
        ? `Đã đăng nhập: ${CloudDB.accountEmail || 'tài khoản Google'}. Mở cùng tài khoản trên điện thoại để xem học phần. Tiến độ học và bản nháp lưu riêng trên thiết bị.`
        : 'Bộ thẻ chỉ lưu trên trình duyệt tại địa chỉ hiện tại. Link Preview Vercel khác không dùng chung dữ liệu; hãy dùng link Production cố định hoặc đăng nhập Google để đồng bộ học phần.';
    document.getElementById('cloud-login').hidden = signedIn;
    document.getElementById('cloud-logout').hidden = !signedIn;
    modal.style.display = 'flex';
}

async function cloudLogin() {
    try {
        if (!window.CloudDB) throw new Error('Không tải được dịch vụ cloud. Kiểm tra mạng rồi thử tải lại trang.');
        await CloudDB.signIn();
        showCloudStatusHelp();
    } catch (error) {
        updateCloudSyncUI('offline', cloudErrorMessage(error));
        showCloudStatusHelp();
        showToast(cloudErrorMessage(error), 8000);
    }
}

async function cloudLogout() {
    try {
        await window.CloudDB?.signOut();
        showCloudStatusHelp();
    } catch (error) { showToast(error.message); }
}

function withCloudTimeout(promise, milliseconds = 12000) {
    let timer;
    return Promise.race([promise, new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('Kết nối cloud quá hạn; dữ liệu vẫn lưu trên máy.')), milliseconds);
    })]).finally(() => clearTimeout(timer));
}

let cloudSyncRunning = null;
let cloudSyncAgain = false;
function syncCloudSets() {
    if (!window.CloudDB || !window.appReady) return Promise.resolve();
    if (cloudSyncRunning) {
        cloudSyncAgain = true;
        return cloudSyncRunning;
    }
    cloudSyncRunning = (async () => {
        do {
            cloudSyncAgain = false;
            await performCloudSync();
        } while (cloudSyncAgain);
    })().finally(() => { cloudSyncRunning = null; });
    return cloudSyncRunning;
}

async function performCloudSync() {
    const client = window.CloudDB;
    const account = client.accountId || null;
    const accountVersion = client.accountVersion;
    const stillCurrent = () => client === window.CloudDB && account === (client.accountId || null) && accountVersion === client.accountVersion;
    updateCloudSyncUI('syncing');
    try {
        // An unsuccessful read MUST reject, never masquerade as an empty catalog.
        const remoteSets = await withCloudTimeout(client.getAllSets());
        if (!Array.isArray(remoteSets)) throw new Error('Phản hồi cloud không hợp lệ.');
        if (!stillCurrent()) return;
        const remoteMap = new Map();
        let conflicts = 0;
        const failures = [];
        for (const raw of remoteSets) {
            let remote;
            try { remote = StudyUtils.normalizeSet(raw); }
            catch (error) { console.warn('Bỏ qua bộ cloud lỗi:', error); continue; }
            remoteMap.set(remote.id, remote);
            if (getDeletedSetIds().includes(remote.id)) continue;
            await Database.updateSet(remote.id, local => {
                if (!stillCurrent() || getDeletedSetIds().includes(remote.id)) return null;
                if (local?.cloudAccount && local.cloudAccount !== (remote.cloudAccount || null)) {
                    conflicts++;
                    return null;
                }
                if (local?.dirty || (local?.isCustom && !local.cloudAccount && !local.cloudRevision)) {
                    if (local.cloudRevision !== remote.cloudRevision &&
                        StudyUtils.contentKey(local) !== StudyUtils.contentKey(remote)) conflicts++;
                    return null;
                }
                if (!local || local.cloudRevision !== remote.cloudRevision ||
                    StudyUtils.contentKey(local) !== StudyUtils.contentKey(remote)) return { ...remote, dirty: false };
                return null;
            });
        }
        if (account) {
            const localSets = await Database.getAllSets();
            for (const snapshot of localSets) {
                if (!stillCurrent()) return;
                const unsynced = snapshot.dirty || (snapshot.isCustom && !snapshot.cloudAccount && !snapshot.cloudRevision);
                if (!unsynced || getDeletedSetIds().includes(String(snapshot.id)) ||
                    (snapshot.cloudAccount && snapshot.cloudAccount !== account)) continue;
                let local;
                try { local = StudyUtils.normalizeSet(snapshot); } catch { continue; }
                const remote = remoteMap.get(local.id);
                if (remote && local.cloudRevision !== remote.cloudRevision &&
                    StudyUtils.contentKey(local) !== StudyUtils.contentKey(remote)) continue;
                try {
                    if (!local.cloudAccount) {
                        const claimed = await Database.updateSet(local.id, latest => {
                            if (!stillCurrent() || !latest || (latest.cloudAccount && latest.cloudAccount !== account) ||
                                latest.localRevision !== local.localRevision) return null;
                            return { ...latest, cloudAccount: account };
                        });
                        if (!claimed) continue;
                        local = claimed;
                    }
                    if (!stillCurrent()) return;
                    const revision = await withCloudTimeout(client.saveSet(local, local.cloudRevision || null));
                    if (!stillCurrent()) return;
                    await Database.updateSet(local.id, latest => {
                        if (!stillCurrent() || !latest || getDeletedSetIds().includes(local.id) ||
                            (latest.cloudAccount && latest.cloudAccount !== account)) return null;
                        return { ...latest, cloudRevision: revision, cloudAccount: account,
                            dirty: latest.localRevision !== local.localRevision };
                    });
                } catch (error) {
                    if (error.code === 'conflict') { conflicts++; continue; }
                    if (!stillCurrent()) return;
                    failures.push(error);
                }
            }
        }
        if (!stillCurrent()) return;
        await loadSetsList(null, { skipCloud: true });
        if (!stillCurrent()) return;
        if (failures.length) {
            updateCloudSyncUI(failures[0].code === 'permission-denied' ? 'locked' : 'offline',
                `${failures.length} học phần chưa đồng bộ. ${cloudErrorMessage(failures[0])}`);
        } else {
            updateCloudSyncUI(conflicts ? 'conflict' : account ? 'connected' : 'catalog',
                conflicts ? 'Có bản sửa khác trên cloud. Bản trên máy được giữ; xuất JSON để lưu cả hai phiên bản.' : '');
        }
        if (conflicts) showToast('Có xung đột đồng bộ. Đã giữ bản trên máy; mở Cloud để xem cách lưu cả hai bản.', 6000);
    } catch (error) {
        if (!stillCurrent()) return;
        updateCloudSyncUI(error.code === 'permission-denied' ? 'locked' : 'offline', cloudErrorMessage(error));
        console.warn('Cloud sync:', error);
    }
}

let cloudInitializing = false;
async function initializeCloud() {
    if (cloudInitializing || window.CloudDB) return;
    cloudInitializing = true;
    updateCloudSyncUI('offline');
    try {
        const [appSDK, fs, authSDK] = await withCloudTimeout(Promise.all([
            import('https://www.gstatic.com/firebasejs/10.13.1/firebase-app.js'),
            import('https://www.gstatic.com/firebasejs/10.13.1/firebase-firestore.js'),
            import('https://www.gstatic.com/firebasejs/10.13.1/firebase-auth.js')
        ]));
        const app = appSDK.initializeApp({
            apiKey: 'AIzaSyDQrqe_dx7jQAitQ9gmrcnY6_TNl2frON0',
            authDomain: 'bhjbhj-c8bdd.firebaseapp.com',
            projectId: 'bhjbhj-c8bdd',
            appId: '1:863761099968:web:841abf121b6ceb18441125'
        });
        const db = fs.getFirestore(app);
        const auth = authSDK.getAuth(app);
        const client = {
            accountId: null,
            accountEmail: null,
            accountVersion: 0,
            accountReady: false,
            signIn: () => authSDK.signInWithPopup(auth, new authSDK.GoogleAuthProvider()),
            signOut: () => authSDK.signOut(auth),
            async getAllSets() {
                const uid = client.accountId;
                const path = uid ? ['users', uid, 'quizlet_sets'] : ['quizlet_sets'];
                const snapshot = await fs.getDocsFromServer(fs.collection(db, ...path));
                return snapshot.docs.map(doc => ({ ...doc.data(), id: doc.id,
                    cloudRevision: doc.data().revision || `legacy:${doc.data().updatedAt || 0}`,
                    cloudAccount: uid, dirty: false, isCustom: !!uid }));
            },
            async saveSet(set, expectedRevision) {
                const uid = client.accountId;
                if (!uid) throw new Error('Cần đăng nhập để đồng bộ bộ thẻ cá nhân.');
                if (set.cloudAccount && set.cloudAccount !== uid) throw new Error('Bộ thẻ thuộc tài khoản khác.');
                const ref = fs.doc(db, 'users', uid, 'quizlet_sets', String(set.id));
                const revision = set.localRevision || crypto.randomUUID();
                return fs.runTransaction(db, async transaction => {
                    if (auth.currentUser?.uid !== uid) throw new Error('Tài khoản đã thay đổi.');
                    const snapshot = await transaction.get(ref);
                    if (auth.currentUser?.uid !== uid) throw new Error('Tài khoản đã thay đổi.');
                    const currentRevision = snapshot.exists()
                        ? snapshot.data().revision || `legacy:${snapshot.data().updatedAt || 0}` : null;
                    if (currentRevision === revision) return revision; // Retry after a timed-out commit.
                    if (currentRevision !== expectedRevision) {
                        const error = new Error('Bản cloud đã thay đổi. Giữ nguyên bản trên máy.');
                        error.code = 'conflict';
                        throw error;
                    }
                    const clean = StudyUtils.normalizeSet(set);
                    transaction.set(ref, { id: clean.id, title: clean.title, description: clean.description,
                        cards: clean.cards, numTerms: clean.cards.length, updatedAt: Date.now(), revision });
                    return revision;
                });
            }
        };
        window.CloudDB = client;
        window.FirebaseDB = db;
        let stopListening = null;
        authSDK.onAuthStateChanged(auth, user => {
            stopListening?.();
            stopListening = null;
            client.accountId = user?.uid || null;
            client.accountEmail = user?.email || user?.displayName || null;
            client.accountVersion++;
            client.accountReady = true;
            try {
                if (user) localStorage.setItem('qp_cloud_account', user.uid);
                else localStorage.removeItem('qp_cloud_account');
            } catch { /* The authenticated session still works without a local cache marker. */ }
            updateCloudSyncUI(user ? 'syncing' : 'catalog');
            if (user) {
                const account = user.uid;
                stopListening = fs.onSnapshot(fs.collection(db, 'users', account, 'quizlet_sets'),
                    { includeMetadataChanges: true }, snapshot => {
                        if (client.accountId === account && window.appReady &&
                            !snapshot.metadata.fromCache && !snapshot.metadata.hasPendingWrites) syncCloudSets();
                    }, error => {
                        if (client.accountId === account) updateCloudSyncUI('locked', cloudErrorMessage(error));
                    });
            }
            if (window.appReady) {
                if (typeof currentSet !== 'undefined' && currentSet?.cloudAccount && currentSet.cloudAccount !== client.accountId) {
                    showDashboard();
                    currentSet = null;
                }
                loadSetsList(null, { skipCloud: true }).catch(error => console.warn('Account library:', error));
            }
            syncCloudSets();
        });
    } catch (error) { updateCloudSyncUI('offline', cloudErrorMessage(error)); }
    finally { cloudInitializing = false; }
}

window.addEventListener('online', () => {
    if (window.CloudDB) syncCloudSets();
    else initializeCloud();
});
function syncCloudOnReturn() {
    if (document.visibilityState !== 'hidden' && window.appReady && window.CloudDB?.accountId) syncCloudSets();
}
document.addEventListener('visibilitychange', syncCloudOnReturn);
window.addEventListener('pageshow', syncCloudOnReturn);
initializeCloud();
