/**
 * ⚙️ BACKEND ROLE - DATA & SRS LOGIC
 * Quản lý IndexedDB cho Quizlet Pro và thuật toán SRS (Spaced Repetition System)
 */

const DB_NAME = 'QuizletProDB';
const DB_VERSION = 2;

const STORE_SETS = 'sets';
const STORE_PROGRESS = 'progress';
const progressKey = (setId, cardId) => JSON.stringify([String(setId), String(cardId)]);

// ==========================================
// 1. KHỞI TẠO & WRAPPER INDEXEDDB
// ==========================================
const dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Bảng Sets: Lưu các bộ thẻ
        if (!db.objectStoreNames.contains(STORE_SETS)) {
            db.createObjectStore(STORE_SETS, { keyPath: 'id' });
        }
        
        // Bảng Progress: Lưu tiến độ học của thẻ (key là tổ hợp setId_cardId)
        if (!db.objectStoreNames.contains(STORE_PROGRESS)) {
            const progressStore = db.createObjectStore(STORE_PROGRESS, { keyPath: 'id' });
            progressStore.createIndex('setId', 'setId', { unique: false });
        } else if (event.oldVersion < 2) {
            const store = request.transaction.objectStore(STORE_PROGRESS);
            const all = store.getAll();
            all.onsuccess = () => {
                store.clear();
                all.result.forEach(p => {
                    p.setId = String(p.setId);
                    p.id = progressKey(p.setId, p.cardId);
                    store.put(p);
                });
            };
        }
        if (event.oldVersion < 2) {
            const sets = request.transaction.objectStore(STORE_SETS);
            const all = sets.getAll();
            all.onsuccess = () => {
                // Retain invalid legacy records for export/repair in the UI.
                const merged = new Map();
                all.result.forEach(set => {
                    const id = String(set.id);
                    if (!merged.has(id) || (set.updatedAt || 0) > (merged.get(id).updatedAt || 0)) merged.set(id, { ...set, id });
                });
                sets.clear();
                merged.forEach(set => sets.put(set));
            };
        }
    };

    request.onsuccess = (event) => {
        const db = event.target.result;
        db.onversionchange = () => db.close();
        resolve(db);
    };
    request.onerror = (event) => reject('Lỗi khởi tạo IndexedDB: ' + event.target.error);
    request.onblocked = () => {
        const message = 'Đóng các tab Quizlet Pro cũ rồi tải lại để nâng cấp bộ nhớ.';
        if (typeof showToast === 'function') showToast(message, 15000);
    };
});

// Hàm tiện ích: Thực thi giao dịch
async function tx(storeName, mode, callback) {
    const db = await dbPromise;
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(storeName, mode);
        const store = transaction.objectStore(storeName);
        let result;
        
        const request = callback(store);
        if (request) {
            request.onsuccess = () => result = request.result;
            request.onerror = () => reject(request.error);
        }

        transaction.oncomplete = () => resolve(result);
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error || new Error('Giao dịch bị hủy.'));
    });
}

async function mutateProgress(setId, cardId, update) {
    const db = await dbPromise;
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE_PROGRESS, 'readwrite');
        const store = transaction.objectStore(STORE_PROGRESS);
        const id = progressKey(setId, cardId);
        let result;
        const request = store.get(id);
        request.onsuccess = () => {
            result = update(request.result || {
                id, setId: String(setId), cardId, box: 0, isStarred: false, nextReview: 0, interval: 0
            });
            store.put(result);
        };
        transaction.oncomplete = () => resolve(result);
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error || new Error('Giao dịch bị hủy.'));
    });
}

// ==========================================
// 2. QUẢN LÝ BỘ THẺ (CRUD SETS)
// ==========================================

const Database = {
    // Lưu một bộ thẻ mới hoặc cập nhật bộ thẻ cũ
    async saveSet(setObj, { preserveTimestamp = false } = {}) {
        setObj = StudyUtils.normalizeSet(setObj);
        if (!preserveTimestamp) setObj.updatedAt = Date.now();
        await tx(STORE_SETS, 'readwrite', store => store.put(setObj));
        return setObj.id;
    },

    // Lấy toàn bộ danh sách các bộ thẻ
    async getAllSets() {
        return await tx(STORE_SETS, 'readonly', store => store.getAll());
    },

    // Lấy chi tiết 1 bộ thẻ theo ID
    async getSetById(setId) {
        return await tx(STORE_SETS, 'readonly', store => store.get(String(setId)));
    },

    // Reconcile cloud state without overwriting an edit made in another tab.
    async updateSet(setId, update) {
        const db = await dbPromise;
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(STORE_SETS, 'readwrite');
            const store = transaction.objectStore(STORE_SETS);
            let result = null;
            const request = store.get(String(setId));
            request.onsuccess = () => {
                try {
                    const next = update(request.result || null);
                    if (next) {
                        result = StudyUtils.normalizeSet(next);
                        store.put(result);
                    }
                } catch (error) { transaction.abort(); reject(error); }
            };
            transaction.oncomplete = () => resolve(result);
            transaction.onerror = () => reject(transaction.error);
            transaction.onabort = () => reject(transaction.error || new Error('Giao dịch bị hủy.'));
        });
    },

    // Xoá bộ thẻ và toàn bộ tiến độ đi kèm
    async deleteSet(setId) {
        setId = String(setId);
        const db = await dbPromise;
        return new Promise((resolve, reject) => {
            const transaction = db.transaction([STORE_SETS, STORE_PROGRESS], 'readwrite');
            transaction.objectStore(STORE_SETS).delete(setId);
            const store = transaction.objectStore(STORE_PROGRESS);
            const index = store.index('setId');
            const request = index.openCursor(IDBKeyRange.only(setId));
            
            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor) {
                    cursor.delete();
                    cursor.continue();
                }
            };
            request.onerror = () => reject(request.error);
            transaction.oncomplete = resolve;
            transaction.onerror = () => reject(transaction.error);
            transaction.onabort = () => reject(transaction.error || new Error('Giao dịch bị hủy.'));
        });
    },

    // Xoá toàn bộ tiến độ học của một bộ thẻ (reset học lại từ đầu)
    async clearProgress(setId) {
        setId = String(setId);
        const db = await dbPromise;
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(STORE_PROGRESS, 'readwrite');
            const store = transaction.objectStore(STORE_PROGRESS);
            const index = store.index('setId');
            const request = index.openCursor(IDBKeyRange.only(setId));
            request.onsuccess = (event) => {
                const cursor = event.target.result;
                if (cursor) {
                    cursor.delete();
                    cursor.continue();
                }
            };
            request.onerror = () => reject(request.error);
            transaction.oncomplete = resolve;
            transaction.onerror = () => reject(transaction.error);
            transaction.onabort = () => reject(transaction.error || new Error('Giao dịch bị hủy.'));
        });
    },

// ==========================================
// 3. THUẬT TOÁN LẶP LẠI NGẮT QUÃNG (SRS)
// ==========================================
    
    // Lấy tiến độ của toàn bộ thẻ trong 1 bộ
    async getProgress(setId) {
        setId = String(setId);
        const db = await dbPromise;
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(STORE_PROGRESS, 'readonly');
            const store = transaction.objectStore(STORE_PROGRESS);
            const index = store.index('setId');
            const request = index.getAll(IDBKeyRange.only(setId));
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
    },

    // Ghi lại toàn bộ tiến độ trong một giao dịch duy nhất.
    // Tránh tạo hàng trăm transaction liên tiếp khi người học chuyển thẻ.
    async saveProgress(setId, progressItems) {
        setId = String(setId);
        const db = await dbPromise;
        const items = Array.isArray(progressItems) ? progressItems : [];
        return new Promise((resolve, reject) => {
            const transaction = db.transaction(STORE_PROGRESS, 'readwrite');
            const store = transaction.objectStore(STORE_PROGRESS);
            const liveIds = new Set(items.map(item => String(item.cardId)));
            const cursorRequest = store.index('setId').openCursor(IDBKeyRange.only(setId));
            cursorRequest.onsuccess = () => {
                const cursor = cursorRequest.result;
                if (!cursor) return;
                if (!liveIds.has(String(cursor.value.cardId))) cursor.delete();
                cursor.continue();
            };
            items.forEach(item => {
                if (!item || item.cardId === undefined) return;
                const progress = {
                    ...item,
                    id: this._getProgressId(setId, item.cardId),
                    setId,
                    cardId: item.cardId,
                    box: Number.isInteger(item.box) ? Math.max(0, Math.min(3, item.box)) : 0,
                    isStarred: !!item.isStarred,
                    nextReview: Number.isFinite(item.nextReview) ? item.nextReview : 0
                };
                store.put(progress);
            });
            transaction.oncomplete = resolve;
            transaction.onerror = () => reject(transaction.error);
            transaction.onabort = () => reject(transaction.error || new Error('Giao dịch IndexedDB bị hủy.'));
        });
    },

    // Lấy ID gộp của tiến độ thẻ
    _getProgressId(setId, cardId) {
        return progressKey(setId, cardId);
    },

    // Thiết lập trực tiếp hộp ghi nhớ chính xác (0: Chưa học, 1: Khó, 2: Đang học, 3: Đã thuộc)
    async setCardBox(setId, cardId, box, isStarred = null) {
        return mutateProgress(setId, cardId, progress => {
            progress.box = Math.max(0, Math.min(3, Number(box) || 0));
            if (isStarred !== null) progress.isStarred = !!isStarred;
            return progress;
        });
    },

    // Cập nhật tiến độ của 1 thẻ sau khi trả lời
    // isCorrect: true (Đúng), false (Sai)
    async updateCardProgress(setId, cardId, isCorrect, isStarred = null) {
        return mutateProgress(setId, cardId, progress => {
            if (isStarred !== null) progress.isStarred = !!isStarred;
            if (typeof isCorrect === 'boolean') {
                const next = StudyUtils.gradeCard({
                    mastery: progress.box === 3 ? 2 : progress.box ? 1 : 0,
                    interval: progress.interval || 0
                }, isCorrect);
                progress.box = !isCorrect ? 1 : next.mastery === 2 ? 3 : 2;
                progress.nextReview = next.nextReview;
                progress.interval = next.interval;
            }
            return progress;
        });
    },

    // Thuật toán chọn thẻ cần học tiếp theo
    async getNextCardsForLearn(setId, allCardsInSet, limit = 10) {
        const progresses = await this.getProgress(setId);
        const map = new Map(progresses.map(p => [String(p.cardId), p]));
        const cards = allCardsInSet.map(card => {
            const progress = map.get(String(card.id));
            return { ...card, mastery: progress?.box === 3 ? 2 : progress?.box ? 1 : 0,
                nextReview: progress?.nextReview || 0 };
        });
        return {
            sessionCards: StudyUtils.reviewQueue(cards).slice(0, limit),
            stats: {
                mastered: cards.filter(c => c.mastery === 2).length,
                learning: cards.filter(c => c.mastery === 1).length,
                unseen: cards.filter(c => c.mastery === 0).length,
                total: allCardsInSet.length
            }
        };
    },

    // Tính toán lại trạng thái (Starred, Tổng thẻ)
    async getSetStats(setId, totalCards) {
        const progresses = await this.getProgress(setId);
        let mastered = 0, learning = 0, starred = 0;
        
        progresses.forEach(p => {
            if (p.isStarred) starred++;
            if (p.box === 3) mastered++;
            else if (p.box === 1 || p.box === 2) learning++;
        });

        const unseen = totalCards - mastered - learning;
        return { mastered, learning, unseen, starred, total: totalCards };
    }
};

window.Database = Database;
