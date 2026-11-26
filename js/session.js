/* A session stores content identity as well as position, so edits invalidate it. */
window.SessionState = {
    read() {
        try { return JSON.parse(localStorage.getItem('qp_active_session') || 'null'); }
        catch { return null; }
    },
    save() {
        if (!currentSet || setLoading || document.getElementById('study-view').style.display === 'none') return;
        const advance = studyPhase === 'advance';
        const snapshot = {
            version: 2, setId: String(currentSet.id), content: StudyUtils.contentKey(currentSet),
            mode: currentMode, settings: JSON.stringify(settings), timestamp: Date.now(),
            queue: currentRoundQueue.map(card => String(card.id)),
            cardIndex: currentCardIndex + (advance ? 1 : 0),
            phase: advance ? 'question' : studyPhase,
            feedback: advance ? null : pendingAnswer,
            writtenInput: advance ? '' : document.getElementById('write-user-input')?.value || '',
            preAnswer: preAnswerProgress,
            fcIndex, fcFlipped, fcIsShuffled,
            fcOrder: fcIsShuffled ? getActiveFlashcardsPool().map(card => String(card.id)) : null,
            test: currentMode === 'test' ? testState : null
        };
        try { localStorage.setItem('qp_active_session', JSON.stringify(snapshot)); }
        catch { showToast('Bộ nhớ trình duyệt đầy; chưa lưu được vị trí phiên học. Hãy xuất bộ thẻ để sao lưu.'); }
    },
    restore(snapshot) {
        if (!snapshot || snapshot.version !== 2 || String(snapshot.setId) !== String(currentSet.id) ||
            snapshot.content !== StudyUtils.contentKey(currentSet) ||
            snapshot.settings !== JSON.stringify(settings) ||
            !['learn', 'write', 'choice', 'flashcards', 'test'].includes(snapshot.mode)) return false;
        const byId = new Map(cardsState.map(card => [String(card.id), card]));
        if (!Array.isArray(snapshot.queue) || snapshot.queue.some(id => !byId.has(id))) return false;
        currentMode = snapshot.mode;
        document.querySelectorAll('[id^="mode-"]').forEach(pill => pill.classList.toggle('active', pill.id === `mode-${currentMode}`));
        syncMobileNav(currentMode === 'flashcards' ? 'flashcards' : 'study');
        const savedIndex = Math.max(0, Math.min(snapshot.cardIndex || 0, snapshot.queue.length));
        const restoredQueue = [];
        const seen = new Set();
        let restoredIndex = 0;
        snapshot.queue.forEach((id, index) => {
            if (index === savedIndex) restoredIndex = restoredQueue.length;
            if (index !== savedIndex && seen.has(id)) return;
            seen.add(id);
            restoredQueue.push(byId.get(id));
        });
        if (savedIndex === snapshot.queue.length) restoredIndex = restoredQueue.length;
        currentRoundQueue = restoredQueue;
        currentCardIndex = Math.max(0, Math.min(restoredIndex, currentRoundQueue.length));
        if (currentMode === 'test') {
            if (!Array.isArray(snapshot.test?.questions) || !snapshot.test.questions.length ||
                snapshot.test.questions.some(q => !byId.has(String(q.cardId)))) return false;
            testState = snapshot.test;
            if (testState.isSubmitted) {
                const correct = testState.questions.filter(q => q.isCorrect).length;
                renderTestResults(correct, testState.questions.length, Math.round(correct / testState.questions.length * 100));
            } else renderTestQuestions();
        } else if (currentMode === 'flashcards') {
            fcIndex = Math.max(0, snapshot.fcIndex || 0);
            fcFlipped = !!snapshot.fcFlipped;
            fcIsShuffled = !!snapshot.fcIsShuffled;
            window._shuffledPool = snapshot.fcOrder?.map(id => byId.get(id)).filter(Boolean) || null;
            renderFlashcardView();
        } else if (snapshot.phase === 'waiting') {
            prepareNextRound();
        } else if (snapshot.phase === 'feedback' && snapshot.feedback && currentRoundQueue[currentCardIndex]) {
            pendingAnswer = snapshot.feedback;
            preAnswerProgress = snapshot.preAnswer;
            const card = currentRoundQueue[currentCardIndex];
            renderFeedback(card, pendingAnswer.userVal, pendingAnswer.correctVal, pendingAnswer.requireRetype);
        } else {
            renderCurrentCard();
            const input = document.getElementById('write-user-input');
            if (input && typeof snapshot.writtenInput === 'string') input.value = snapshot.writtenInput;
        }
        return true;
    }
};

window.addEventListener('pagehide', () => {
    if (window.saveActiveSession) saveActiveSession();
    if (window.saveEditorDraft) saveEditorDraft();
});
