/**
 * ⚙️ BACKEND ROLE - DATA & SRS LOGIC
 * Quản lý IndexedDB cho Quizlet Pro và thuật toán SRS (Spaced Repetition System)
 */

const DB_NAME = 'QuizletProDB';
const DB_VERSION = 1;

const STORE_SETS = 'sets';
const STORE_PROGRESS = 'progress';

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
        }
    };

    request.onsuccess = (event) => resolve(event.target.result);
    request.onerror = (event) => reject('Lỗi khởi tạo IndexedDB: ' + event.target.error);
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
    });
}

// ==========================================
// 2. QUẢN LÝ BỘ THẺ (CRUD SETS)
// ==========================================

const Database = {
    // Lưu một bộ thẻ mới hoặc cập nhật bộ thẻ cũ
    async saveSet(setObj) {
        if (!setObj.id) setObj.id = 'set_' + Date.now();
        setObj.updatedAt = Date.now();
        await tx(STORE_SETS, 'readwrite', store => store.put(setObj));
        return setObj.id;
    },

    // Lấy toàn bộ danh sách các bộ thẻ
    async getAllSets() {
        return await tx(STORE_SETS, 'readonly', store => store.getAll());
    },

    // Lấy chi tiết 1 bộ thẻ theo ID
    async getSetById(setId) {
        return await tx(STORE_SETS, 'readonly', store => store.get(setId));
    },

    // Xoá bộ thẻ và toàn bộ tiến độ đi kèm
    async deleteSet(setId) {
        await tx(STORE_SETS, 'readwrite', store => store.delete(setId));
        
        // Cần xoá tiến độ đi kèm (tìm index bằng setId)
        const db = await dbPromise;
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
    },

// ==========================================
// 3. THUẬT TOÁN LẶP LẠI NGẮT QUÃNG (SRS)
// ==========================================
    
    // Lấy tiến độ của toàn bộ thẻ trong 1 bộ
    async getProgress(setId) {
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

    // Lấy ID gộp của tiến độ thẻ
    _getProgressId(setId, cardId) {
        return `${setId}_${cardId}`;
    },

    // Cập nhật tiến độ của 1 thẻ sau khi trả lời
    // isCorrect: true (Đúng), false (Sai)
    async updateCardProgress(setId, cardId, isCorrect, isStarred = null) {
        const progId = this._getProgressId(setId, cardId);
        let prog = await tx(STORE_PROGRESS, 'readonly', store => store.get(progId));

        if (!prog) {
            prog = {
                id: progId,
                setId: setId,
                cardId: cardId,
                box: 0,           // 0: Unseen, 1: Khó, 2: Đang học, 3: Đã biết
                isStarred: false,
                nextReview: 0
            };
        }

        if (isStarred !== null) {
            prog.isStarred = isStarred;
        }

        // --- THUẬT TOÁN SRS CỐT LÕI ---
        const now = Date.now();
        if (isCorrect === false) {
            // Sai -> Rớt thẳng về Hộp 1 (Khó), ôn lại ngay lập tức (sau 0 phút)
            prog.box = 1;
            prog.nextReview = now; 
        } else if (isCorrect === true) {
            // Đúng -> Thăng cấp
            if (prog.box === 0 || prog.box === 1) {
                // Đang từ Chưa học/Khó -> Lên Đang học (Hộp 2), ôn lại sau 5 phút
                prog.box = 2;
                prog.nextReview = now + 5 * 60 * 1000;
            } else if (prog.box === 2) {
                // Đang từ Đang học -> Lên Đã biết (Hộp 3 - Mastered), coi như xong session này
                prog.box = 3;
                // Nếu học lâu dài có thể set ngày mai: now + 24 * 60 * 60 * 1000
                prog.nextReview = now + 24 * 60 * 60 * 1000;
            }
        }
        
        await tx(STORE_PROGRESS, 'readwrite', store => store.put(prog));
        return prog;
    },

    // Thuật toán chọn thẻ cần học tiếp theo
    async getNextCardsForLearn(setId, allCardsInSet, limit = 10) {
        const progresses = await this.getProgress(setId);
        const progMap = new Map();
        progresses.forEach(p => progMap.set(p.cardId, p));

        const now = Date.now();
        let box1 = []; // Khó (Sai)
        let box0 = []; // Chưa học
        let box2 = []; // Đang học (Đã đến giờ review)
        let box3 = []; // Đã biết (Không lấy vào session hiện tại trừ khi học lại từ đầu)

        allCardsInSet.forEach(card => {
            const p = progMap.get(card.id);
            if (!p) {
                box0.push(card);
            } else if (p.box === 1) {
                box1.push(card);
            } else if (p.box === 2 && now >= p.nextReview) {
                box2.push(card);
            } else if (p.box === 3) {
                box3.push(card);
            }
        });

        // Xáo trộn mảng
        const shuffle = arr => arr.sort(() => Math.random() - 0.5);

        // Thứ tự ưu tiên: Khó (Box 1) -> Đã đến giờ (Box 2) -> Chưa học (Box 0)
        let sessionCards = [];
        sessionCards = sessionCards.concat(shuffle(box1));
        sessionCards = sessionCards.concat(shuffle(box2));
        
        // Nếu thiếu thẻ, bốc thêm từ Chưa học
        if (sessionCards.length < limit && box0.length > 0) {
            const need = limit - sessionCards.length;
            sessionCards = sessionCards.concat(shuffle(box0).slice(0, need));
        }

        return {
            sessionCards: sessionCards.slice(0, limit),
            stats: {
                mastered: box3.length,
                learning: box1.length + box2.length,
                unseen: box0.length,
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
        return { mastered, learning, unseen, starred, total };
    }
};

window.Database = Database;
