/* Header, search and import controls shared by desktop and mobile. */
function hideAllDropdowns() {
    document.querySelectorAll('.create-dropdown-menu, .profile-dropdown-menu')
        .forEach(menu => { menu.style.display = 'none'; });
}

function toggleDropdown(event, id) {
    event.stopPropagation();
    const menu = document.getElementById(id);
    const opening = menu.style.display === 'none';
    hideAllDropdowns();
    menu.style.display = opening ? 'block' : 'none';
}

function toggleCreateDropdown(event) {
    toggleDropdown(event, 'create-dropdown-menu');
}

function toggleProfileDropdown(event) {
    toggleDropdown(event, 'profile-dropdown-menu');
}

document.addEventListener('click', event => {
    if (!event.target.closest('.create-dropdown-wrap, .profile-dropdown-wrap')) hideAllDropdowns();
});

function openQuickImportModal(tab = 'link') {
    closeAllModals();
    hideAllDropdowns();
    document.getElementById('quick-import-modal').style.display = 'flex';
    switchImportTab(tab);
}

function closeQuickImportModal() {
    document.getElementById('quick-import-modal').style.display = 'none';
}

function switchImportTab(tab) {
    if (!['link', 'paste', 'guide'].includes(tab)) tab = 'link';
    ['link', 'paste', 'guide'].forEach(name => {
        document.getElementById(`import-pane-${name}`).style.display = name === tab ? 'block' : 'none';
        document.getElementById(`import-tab-${name}`).classList.toggle('active', name === tab);
    });
    if (tab !== 'guide') document.getElementById(tab === 'link' ? 'modal-scrape-url' : 'quick-import-text').focus();
}

async function triggerModalScrape() {
    const button = document.getElementById('btn-modal-scrape');
    document.getElementById('scrape-url-input').value = document.getElementById('modal-scrape-url').value;
    button.disabled = true;
    try {
        await triggerScrape();
    } finally {
        button.disabled = false;
    }
}

async function submitQuickImportText() {
    const text = document.getElementById('quick-import-text').value;
    if (!text.trim()) {
        showToast('Hãy dán nội dung bộ thẻ trước khi nhập.');
        return;
    }
    try {
        await parseAndImportText(text, document.getElementById('quick-import-title').value.trim() || null);
    } catch (error) {
        showToast(`Không thể nhập thẻ: ${error.message}`);
    }
}

function searchKey(value) {
    return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase().trim();
}

function filterDashboardSets(query) {
    const grid = document.getElementById('dash-sets-grid');
    const key = searchKey(query);
    if (grid) grid.innerHTML = renderSetsGrid((window.allDashboardSets || [])
        .filter(set => searchKey(set.title).includes(key)));
}

function isQuizletLink(value) {
    try {
        const url = new URL(value.trim());
        return ['http:', 'https:'].includes(url.protocol) &&
            (url.hostname === 'quizlet.com' || url.hostname === 'www.quizlet.com');
    } catch {
        return false;
    }
}

function handleGlobalSearch(value) {
    const link = isQuizletLink(value);
    document.getElementById('btn-smart-action').style.display = link ? 'flex' : 'none';
    if (link) return;
    if (document.getElementById('study-view').style.display !== 'none') {
        filterTermsOverview(value);
    } else {
        filterDashboardSets(value);
    }
}

function executeGlobalSearch(value) {
    if (isQuizletLink(value)) {
        openQuickImportModal('link');
        document.getElementById('modal-scrape-url').value = value.trim();
    } else {
        handleGlobalSearch(value);
    }
}

function executeSmartAction() {
    executeGlobalSearch(document.getElementById('global-search-input').value);
}

// Dialogs must not inherit display:none from the study view on the home screen.
document.body.appendChild(document.getElementById('mobile-bottom-bar'));
document.querySelectorAll('.modal-overlay').forEach(modal => {
    document.body.appendChild(modal);
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    const title = modal.querySelector('.modal-header');
    if (title) {
        if (!title.id) title.id = `${modal.id}-title`;
        modal.setAttribute('aria-labelledby', title.id);
    }
});

// Focus and inert state follow every modal, including legacy inline handlers.
let activeModal = null;
let modalReturnFocus = null;
let lastOutsideFocus = null;
let previousBodyOverflow = '';
const inertBeforeModal = new Map();
function modalFocusables(modal) {
    return [...modal.querySelectorAll('button, a[href], input, select, textarea, [tabindex]')]
        .filter(el => !el.disabled && el.tabIndex >= 0 && !el.hidden && el.getClientRects().length);
}
function syncModalFocus() {
    const open = [...document.querySelectorAll('.modal-overlay')]
        .filter(modal => modal.style.display !== 'none' && modal.getClientRects().length);
    const newlyOpened = open.find(modal => modal !== activeModal);
    const next = newlyOpened || open[0] || null;
    if (next === activeModal) return;
    if (next) {
        if (!activeModal) {
            modalReturnFocus = next.contains(document.activeElement) ? lastOutsideFocus : document.activeElement;
            previousBodyOverflow = document.body.style.overflow;
        }
        if (activeModal && activeModal !== next) activeModal.style.display = 'none';
        activeModal = next;
        next.tabIndex = -1;
        for (const element of document.body.children) {
            if (element.matches('script, style')) continue;
            if (!inertBeforeModal.has(element)) inertBeforeModal.set(element, element.inert);
            element.inert = element !== next;
        }
        document.body.style.overflow = 'hidden';
        (modalFocusables(next)[0] || next).focus();
    } else {
        activeModal = null;
        for (const [element, inert] of inertBeforeModal) element.inert = inert;
        inertBeforeModal.clear();
        document.body.style.overflow = previousBodyOverflow;
        if (modalReturnFocus?.isConnected && !modalReturnFocus.closest('[inert]')) modalReturnFocus.focus();
        modalReturnFocus = null;
    }
}
const modalObserver = new MutationObserver(syncModalFocus);
document.addEventListener('focusin', event => {
    if (!event.target.closest('.modal-overlay')) lastOutsideFocus = event.target;
});
document.addEventListener('click', event => {
    if (!event.target.closest('.modal-overlay')) {
        lastOutsideFocus = event.target.closest('button, a, [tabindex]') || document.activeElement;
    }
}, true);
document.querySelectorAll('.modal-overlay').forEach(modal =>
    modalObserver.observe(modal, { attributes: true, attributeFilter: ['style'] }));

document.addEventListener('keydown', event => {
    syncModalFocus();
    if (!activeModal) return;
    if (event.key === 'Escape') {
        event.preventDefault();
        activeModal.style.display = 'none';
        syncModalFocus();
    } else if (event.key === 'Tab') {
        const items = modalFocusables(activeModal);
        if (!items.length) {
            event.preventDefault();
            activeModal.focus();
            return;
        }
        const first = items[0], last = items[items.length - 1];
        if (!activeModal.contains(document.activeElement) ||
            (event.shiftKey && document.activeElement === first) ||
            (!event.shiftKey && document.activeElement === last)) {
            event.preventDefault();
            (event.shiftKey ? last : first).focus();
        }
    }
}, true);

function makeControlsKeyboardAccessible(root = document) {
    root.querySelectorAll('.dropdown-item, .set-card-modern[onclick], .brand, .avatar-circle-modern, .cloud-status-pill, .fc-wrapper, .match-tile')
        .forEach(element => {
            element.tabIndex = 0;
            element.setAttribute('role', 'button');
        });
}
makeControlsKeyboardAccessible();
new MutationObserver(() => makeControlsKeyboardAccessible()).observe(document.body, { childList: true, subtree: true });
document.addEventListener('keydown', event => {
    if (event.isComposing || !['Enter', ' '].includes(event.key)) return;
    if (event.target.matches('[role="button"]:not(button):not(input)')) {
        event.preventDefault();
        event.stopPropagation();
        event.target.click();
    }
}, true);

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(error => console.warn('Offline cache:', error));
    });
}
