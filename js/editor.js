function getEditorDrafts() {
    try {
        const drafts = JSON.parse(localStorage.getItem('qp_editor_drafts') || '{}');
        return drafts && typeof drafts === 'object' && !Array.isArray(drafts) ? drafts : {};
    }
    catch { return {}; }
}

function saveEditorDraft() {
    if (document.getElementById('create-set-view').style.display === 'none' || window.restoringDraft || window.initializingEditor) return;
    const key = currentEditingSetId == null ? 'new' : String(currentEditingSetId);
    const cards = [...document.querySelectorAll('#create-cards-list .card-row')].map(row => {
        if (!row.dataset.draftId) row.dataset.draftId = crypto.randomUUID();
        return { id: row.originalCard?.id ?? row.dataset.draftId,
            term: row.querySelector('.term-input').value,
            definition: row.querySelector('.def-input').value,
            image: row.querySelector('.image-input')?.value.trim() ?? row.originalCard?.image ?? '' };
    });
    const draft = { editingId: currentEditingSetId, title: document.getElementById('create-title').value,
        description: document.getElementById('create-desc').value, cards, updatedAt: Date.now(),
        importText: document.getElementById('import-raw-text').value,
        importSettings: Object.fromEntries(['termSep', 'cardSep'].map(name => [name, document.querySelector(`input[name="${name}"]:checked`).value])),
        termSepCustom: document.getElementById('termSepCustom').value,
        cardSepCustom: document.getElementById('cardSepCustom').value };
    if (!draft.title.trim() && !draft.description.trim() && !draft.importText.trim() && cards.every(c => !c.term.trim() && !c.definition.trim() && !c.image)) {
        clearEditorDraft(key);
        return;
    }
    try {
        const drafts = getEditorDrafts();
        drafts[key] = draft;
        localStorage.setItem('qp_editor_drafts', JSON.stringify(drafts));
        localStorage.setItem('qp_active_draft', key);
    } catch { showToast('Bộ nhớ đầy; chưa lưu được bản nháp. Hãy lưu/xuất bộ thẻ trước khi đóng trang.'); }
}

function restoreDraftFor(key) {
    const draft = getEditorDrafts()[key];
    if (!draft) return false;
    window.restoringDraft = true;
    try {
        currentEditingSetId = draft.editingId;
        document.getElementById('create-title').value = draft.title || '';
        document.getElementById('create-desc').value = draft.description || '';
        document.getElementById('import-raw-text').value = draft.importText || '';
        for (const name of ['termSep', 'cardSep']) {
            const value = draft.importSettings?.[name];
            const radio = [...document.querySelectorAll(`input[name="${name}"]`)].find(input => input.value === value);
            if (radio) radio.checked = true;
            document.getElementById(`${name}Custom`).value = draft[`${name}Custom`] || '';
        }
        document.getElementById('import-box-ui').style.display = draft.importText ? 'block' : 'none';
        updateImportPreview();
        document.getElementById('create-cards-list').replaceChildren();
        (draft.cards || []).forEach(card => addCardRow(card.term, card.definition, card));
        if (!draft.cards?.length) addCardRow();
    } finally { window.restoringDraft = false; }
    return true;
}

function restoreEditorDraft(key = localStorage.getItem('qp_active_draft')) {
    if (!key || !getEditorDrafts()[key]) return;
    saveEditorDraft();
    window.restoringDraft = true;
    showCreateSetView();
    window.restoringDraft = false;
    restoreDraftFor(key);
    document.getElementById('create-view-heading').textContent = currentEditingSetId == null ? 'Tiếp tục bản nháp' : '✏️ Tiếp tục chỉnh sửa học phần';
    document.querySelectorAll('#btn-save-set-top, #btn-save-set-bottom').forEach(button => {
        button.textContent = currentEditingSetId == null ? 'Tạo' : '💾 Lưu thay đổi';
    });
    localStorage.setItem('qp_active_draft', key);
    showToast('Đã khôi phục bản nháp trên thiết bị này.');
}

function clearEditorDraft(key) {
    const drafts = getEditorDrafts();
    delete drafts[key];
    try {
        localStorage.setItem('qp_editor_drafts', JSON.stringify(drafts));
        if (localStorage.getItem('qp_active_draft') === String(key)) localStorage.removeItem('qp_active_draft');
    } catch { showToast('Chưa xóa được bản nháp khỏi bộ nhớ thiết bị.'); }
}

function renderDraftBanner() {
    document.getElementById('draft-banner')?.remove();
    const drafts = Object.entries(getEditorDrafts());
    if (!drafts.length) return;
    const banner = document.createElement('div');
    banner.id = 'draft-banner';
    banner.style.cssText = 'margin-bottom:20px;display:flex;gap:8px;flex-wrap:wrap';
    for (const [key, draft] of drafts) {
        const button = document.createElement('button');
        button.className = 'btn-cancel';
        button.textContent = `Tiếp tục bản nháp: ${draft.title || 'Chưa đặt tên'}`;
        button.onclick = () => restoreEditorDraft(key);
        banner.append(button);
        const discard = document.createElement('button');
        discard.className = 'btn-cancel';
        discard.title = 'Bỏ bản nháp';
        discard.setAttribute('aria-label', `Bỏ bản nháp: ${draft.title || 'Chưa đặt tên'}`);
        discard.textContent = '🗑️';
        discard.onclick = () => {
            if (!confirm('Bỏ bản nháp này? Nội dung chưa lưu sẽ bị xóa.')) return;
            clearEditorDraft(key);
            renderDraftBanner();
        };
        banner.append(discard);
    }
    document.getElementById('dashboard-view').prepend(banner);
}

async function repairStoredSet(id) {
    const raw = await Database.getSetById(id);
    if (!raw) return showToast('Không tìm thấy bản gốc trên máy.');
    currentSet = { ...raw, cards: Array.isArray(raw.cards) ? raw.cards.filter(Boolean).map(c => ({
        ...c, term: String(c.term ?? ''), definition: String(c.definition ?? '')
    })) : [] };
    setLoading = false;
    openEditCurrentSet();
}

function downloadJSON(value, filename) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function exportStoredSet(id) {
    const raw = await Database.getSetById(id);
    if (raw) downloadJSON(raw, 'hoc-phan-ban-goc.json');
}

async function copyCurrentSet() {
    if (!currentSet) return showToast('Mở bộ thẻ muốn giữ thành bản sao trước.');
    try {
        const copy = { ...currentSet, id: `set_${crypto.randomUUID()}`, title: `${currentSet.title} (bản sao)` };
        await saveCustomSet(copy);
        closeAllModals();
        await loadSetsList(copy.id);
    } catch (error) { showToast(error.message); }
}

function resetEditorImport() {
    document.getElementById('import-raw-text').value = '';
    document.getElementById('import-box-ui').style.display = 'none';
    document.querySelector('input[name="termSep"][value="tab"]').checked = true;
    document.querySelector('input[name="cardSep"][value="newline"]').checked = true;
    document.getElementById('termSepCustom').value = '';
    document.getElementById('cardSepCustom').value = '';
    updateImportPreview();
}

document.getElementById('create-set-view').addEventListener('input', saveEditorDraft);
document.getElementById('create-set-view').addEventListener('change', saveEditorDraft);

const fileLabel = document.createElement('label');
fileLabel.className = 'btn-cancel';
fileLabel.style.cssText = 'display:block;margin:12px 0;cursor:pointer';
fileLabel.textContent = 'Chọn file JSON để nhập ';
const fileInput = document.createElement('input');
fileInput.id = 'import-json-file';
fileInput.type = 'file';
fileInput.accept = '.json,application/json';
fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    try {
        if (file.size > 5 * 1024 * 1024) throw new Error('File vượt quá 5 MB.');
        const raw = await file.text();
        const parsed = JSON.parse(raw);
        StudyUtils.requireCompleteCards(StudyUtils.normalizeSet(parsed));
        await parseAndImportText(raw);
    } catch (error) { showToast(`Không nhập được file: ${error.message}`, 6000); }
    finally { fileInput.value = ''; }
});
fileLabel.append(fileInput);
document.getElementById('import-pane-paste').prepend(fileLabel);
