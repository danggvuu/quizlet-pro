/* Local-first cloud synchronization. SDK failure never removes the local UI. */
function updateCloudSyncUI(status, message = '') {
    const badge = document.getElementById('cloud-status-badge');
    if (!badge) return;
    const labels = { connected: 'Đã đồng bộ', syncing: 'Đang đồng bộ', conflict: 'Có xung đột',
        offline: 'Lưu trên máy', locked: 'Chưa có quyền', catalog: 'Thư viện chung' };
    badge.className = `cloud-status-pill ${status === 'connected' ? 'online' : 'offline'}`;
    document.getElementById('cloud-status-text').textContent = labels[status] || labels.offline;
    badge.title = message || labels[status] || labels.offline;
}

function showCloudStatusHelp() {
    const modal = document.getElementById('cloud-account-modal');
    const signedIn = !!window.CloudDB?.accountId;
    document.getElementById('cloud-account-info').textContent = signedIn
        ? 'Bộ thẻ cá nhân đồng bộ theo tài khoản Google. Tiến độ học vẫn lưu riêng trên máy này.'
        : 'Bộ thẻ đang được lưu trên máy. Đăng nhập Google để đồng bộ nội dung giữa các thiết bị của bạn.';
    document.getElementById('cloud-login').hidden = signedIn;
    document.getElementById('cloud-logout').hidden = !signedIn;
    modal.style.display = 'flex';
}

async function cloudLogin() {
    try {
        if (!window.CloudDB) throw new Error('Không tải được dịch vụ cloud. Kiểm tra mạng rồi thử tải lại trang.');
        await CloudDB.signIn();
        showCloudStatusHelp();
    } catch (error) { showToast(`Chưa đăng nhập được: ${error.message}`); }
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
    cloudSyncRunning = performCloudSync().finally(() => {
        cloudSyncRunning = null;
        if (cloudSyncAgain) {
            cloudSyncAgain = false;
            syncCloudSets();
        }
    });
    return cloudSyncRunning;
}

async function performCloudSync() {
    const client = window.CloudDB;
    const account = client.accountId || null;
    const stillCurrent = () => client === window.CloudDB && account === (client.accountId || null);
    updateCloudSyncUI('syncing');
    try {
        // An unsuccessful read MUST reject, never masquerade as an empty catalog.
        const remoteSets = await withCloudTimeout(client.getAllSets());
        if (!Array.isArray(remoteSets)) throw new Error('Phản hồi cloud không hợp lệ.');
        if (!stillCurrent()) return;
        const remoteMap = new Map();
        let conflicts = 0;
        for (const raw of remoteSets) {
            let remote;
            try { remote = StudyUtils.normalizeSet(raw); }
            catch (error) { console.warn('Bỏ qua bộ cloud lỗi:', error); continue; }
            remoteMap.set(remote.id, remote);
            if (getDeletedSetIds().includes(remote.id)) continue;
            const local = await Database.getSetById(remote.id);
            if (!stillCurrent()) return;
            if (local?.cloudAccount && local.cloudAccount !== (remote.cloudAccount || null)) {
                // Switching accounts must not replace another account's local copy.
                conflicts++;
                continue;
            }
            if (local?.dirty) {
                if (local.cloudRevision !== remote.cloudRevision &&
                    StudyUtils.contentKey(local) !== StudyUtils.contentKey(remote)) {
                    conflicts++;
                }
                continue;
            }
            if (!local || local.cloudRevision !== remote.cloudRevision ||
                StudyUtils.contentKey(local) !== StudyUtils.contentKey(remote)) {
                if (getDeletedSetIds().includes(remote.id)) continue;
                await Database.saveSet({ ...remote, dirty: false }, { preserveTimestamp: true });
            }
        }
        if (account) {
            const localSets = await Database.getAllSets();
            for (const snapshot of localSets) {
                if (!stillCurrent()) return;
                if (!snapshot.dirty || getDeletedSetIds().includes(String(snapshot.id)) ||
                    (snapshot.cloudAccount && snapshot.cloudAccount !== account)) continue;
                let local;
                try { local = StudyUtils.normalizeSet(snapshot); } catch { continue; }
                const remote = remoteMap.get(local.id);
                if (remote && local.cloudRevision !== remote.cloudRevision &&
                    StudyUtils.contentKey(local) !== StudyUtils.contentKey(remote)) continue;
                try {
                    const revision = await withCloudTimeout(client.saveSet(local, local.cloudRevision || null));
                    if (!stillCurrent()) return;
                    const latest = await Database.getSetById(local.id);
                    if (!latest || getDeletedSetIds().includes(local.id)) continue;
                    // Do not clear a newer edit that was made while the network was busy.
                    await Database.saveSet({ ...latest, cloudRevision: revision, cloudAccount: account,
                        dirty: latest.localRevision !== local.localRevision }, { preserveTimestamp: true });
                } catch (error) {
                    if (error.code === 'conflict') { conflicts++; continue; }
                    throw error;
                }
            }
        }
        if (!stillCurrent()) return;
        await loadSetsList(null, { skipCloud: true });
        updateCloudSyncUI(conflicts ? 'conflict' : account ? 'connected' : 'catalog',
            conflicts ? 'Có bản sửa khác trên cloud. Bản trên máy được giữ; xuất JSON để lưu cả hai phiên bản.' : '');
        if (conflicts) showToast('Có xung đột đồng bộ. Đã giữ bản trên máy; mở Cloud để xem cách lưu cả hai bản.', 6000);
    } catch (error) {
        updateCloudSyncUI(error.code === 'permission-denied' ? 'locked' : 'offline', error.message);
        console.warn('Cloud sync:', error);
    }
}

async function initializeCloud() {
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
                const ref = fs.doc(db, 'users', uid, 'quizlet_sets', String(set.id));
                const revision = set.localRevision || crypto.randomUUID();
                return fs.runTransaction(db, async transaction => {
                    if (auth.currentUser?.uid !== uid) throw new Error('Tài khoản đã thay đổi.');
                    const snapshot = await transaction.get(ref);
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
        authSDK.onAuthStateChanged(auth, user => {
            client.accountId = user?.uid || null;
            syncCloudSets();
        });
    } catch (error) { updateCloudSyncUI('offline', error.message); }
}

window.addEventListener('online', () => {
    if (window.CloudDB) syncCloudSets();
    else initializeCloud();
});
initializeCloud();
