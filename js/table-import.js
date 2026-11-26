(function (root) {
    function parseWithDelimiter(text, delimiter) {
        const rows = [];
        let row = [], cell = '', quoted = false;
        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            if (quoted) {
                if (char === '"' && text[i + 1] === '"') { cell += '"'; i++; }
                else if (char === '"') quoted = false;
                else if (char === '\r' && text[i + 1] === '\n') { cell += '\n'; i++; }
                else cell += char;
                continue;
            }
            if (char === '"' && !cell.trim()) { cell = ''; quoted = true; }
            else if (text.startsWith(delimiter, i)) { row.push(cell); cell = ''; i += delimiter.length - 1; }
            else if (char === '\n' || char === '\r') {
                if (char === '\r' && text[i + 1] === '\n') i++;
                row.push(cell); rows.push(row); row = []; cell = '';
            } else cell += char;
        }
        if (quoted) throw new Error('Có ô CSV mở dấu ngoặc kép nhưng chưa đóng.');
        if (cell || row.length) { row.push(cell); rows.push(row); }
        return rows;
    }

    function detectDelimiter(text) {
        const candidates = ['\t', ',', ';', '|', ':', '：', '、'];
        let best = { delimiter: '\t', score: -1 };
        for (const delimiter of candidates) {
            let rows;
            try { rows = parseWithDelimiter(text, delimiter); }
            catch { continue; }
            const counts = rows.filter(row => row.some(value => value.trim()))
                .map(row => row.length).filter(count => count > 1);
            if (!counts.length) continue;
            const frequencies = new Map();
            counts.forEach(count => frequencies.set(count, (frequencies.get(count) || 0) + 1));
            const [width, consistent] = [...frequencies.entries()].sort((a, b) => b[1] - a[1] || b[0] - a[0])[0];
            const score = consistent * 100 + width;
            if (score > best.score) best = { delimiter, score };
        }
        return best.delimiter;
    }

    function parseDelimited(input, requestedDelimiter = 'auto') {
        const text = String(input ?? '').replace(/^\uFEFF/, '');
        const delimiter = requestedDelimiter === 'auto' ? detectDelimiter(text) : requestedDelimiter;
        if (typeof delimiter !== 'string' || !delimiter.length || /[\r\n"]/.test(delimiter)) {
            throw new Error('Hãy nhập dấu phân cách cột, không dùng xuống dòng hoặc dấu ngoặc kép.');
        }
        return { delimiter, rows: parseWithDelimiter(text, delimiter) };
    }

    const HEADER_ROLES = {
        term: /(^|[^a-z])(term|word|front|question|prompt|vocabulary|expression|tu|tu vung|thuat ngu|cau hoi|mat truoc)(?=$|[^a-z])/i,
        definition: /(^|[^a-z])(definition|meaning|back|answer|translation|nghia|dinh nghia|dap an|mat sau)(?=$|[^a-z])/i
    };

    function normalizeHeader(value) {
        return String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
            .replace(/đ/g, 'd').replace(/Đ/g, 'D').trim().toLowerCase();
    }

    function guessHeaderRow(rows) {
        const terms = new Set(['term', 'word', 'front', 'question', 'prompt', 'vocabulary', 'expression', 'tu', 'tu vung', 'thuat ngu', 'cau hoi', 'mat truoc']);
        const definitions = new Set(['definition', 'meaning', 'back', 'answer', 'translation', 'nghia', 'dinh nghia', 'dap an', 'mat sau']);
        const languageColumns = new Set(['english', 'vietnamese', 'french', 'spanish', 'german', 'japanese', 'korean', 'chinese']);
        for (let index = 0; index < Math.min(rows.length, 20); index++) {
            const recognized = rows[index].filter(value => {
                const header = normalizeHeader(value);
                return terms.has(header) || definitions.has(header) || languageColumns.has(header);
            }).length;
            if (recognized >= 2) return index;
        }
        return -1;
    }

    function guessHasHeader(rows) {
        return guessHeaderRow(rows) === 0;
    }

    function guessRoles(headers) {
        const roles = headers.map(header => {
            const value = normalizeHeader(header);
            if (HEADER_ROLES.term.test(value)) return 'term';
            if (HEADER_ROLES.definition.test(value)) return 'definition';
            return 'ignore';
        });
        if (!roles.includes('term') && roles.length) roles[0] = 'term';
        if (!roles.includes('definition') && roles.length > 1) {
            const index = roles.findIndex(role => role === 'ignore');
            roles[index < 0 ? 1 : index] = 'definition';
        }
        return roles;
    }

    function mapRows(rows, hasHeader, roles) {
        const headerIndex = hasHeader === true ? 0 : hasHeader === false ? -1 : Number(hasHeader);
        const hasHeaderRow = Number.isInteger(headerIndex) && headerIndex >= 0 && headerIndex < rows.length;
        const headers = (hasHeaderRow ? rows[headerIndex] || [] : (rows[0] || []).map((_, index) => `Cột ${index + 1}`))
            .map((header, index) => String(header || `Cột ${index + 1}`).trim());
        const data = hasHeaderRow ? rows.slice(headerIndex + 1) : rows;
        const cards = [], invalidRows = [];
        data.forEach((values, index) => {
            const cells = headers.map((_, column) => String(values[column] ?? '').trim());
            if (!cells.some(Boolean)) return;
            const collect = (role, extraRole) => {
                const primary = [], extras = [];
                roles.forEach((value, column) => {
                    const cell = cells[column];
                    if (!cell) return;
                    if (value === role) primary.push(cell);
                    if (value === extraRole) extras.push(`${headers[column]}: ${cell}`);
                });
                return [...primary, ...extras].join('\n').trim();
            };
            const term = collect('term', 'term-extra');
            const definition = collect('definition', 'definition-extra');
            if (!term || !definition) {
                invalidRows.push({ row: index + (hasHeaderRow ? headerIndex + 2 : 1), missing: [!term && 'thuật ngữ', !definition && 'định nghĩa'].filter(Boolean) });
            } else cards.push({ term, definition });
        });
        return { headers, cards, invalidRows };
    }

    const api = { parseDelimited, guessHeaderRow, guessHasHeader, guessRoles, mapRows };
    root.TableImport = api;
    if (typeof module !== 'undefined') module.exports = api;
    if (!root.document) return;

    const MAX_FILE_BYTES = 10 * 1024 * 1024;
    const MAX_TEXT_BYTES = 2 * 1024 * 1024;
    const MAX_ROWS = 20000;
    let target = 'new';
    let rows = [];
    let workbook = null;
    let textSource = null;
    let roles = [];
    let xlsxPromise = null;

    const byId = id => document.getElementById(id);
    const setError = message => {
        const error = byId('table-import-error');
        error.textContent = message || '';
        error.hidden = !message;
    };

    function clearSource() {
        rows = [];
        workbook = null;
        textSource = null;
        roles = [];
        byId('table-import-text').value = '';
        byId('table-import-file').value = '';
        byId('table-import-sheet').replaceChildren();
        byId('table-import-sheet-wrap').hidden = true;
        byId('table-import-source').textContent = 'Chọn file hoặc dán bảng vào ô bên dưới.';
        byId('table-import-header-row').replaceChildren(new Option('Không có tiêu đề', '0'));
        setError('');
        render();
    }

    function openTableImporter(nextTarget = 'new') {
        target = nextTarget === 'editor' ? 'editor' : 'new';
        byId('table-import-delimiter').value = 'auto';
        byId('table-import-delimiter-custom').value = '';
        clearSource();
        byId('table-import-title-wrap').hidden = target !== 'new';
        byId('table-import-submit').textContent = target === 'editor' ? 'Thêm vào bộ đang sửa' : 'Tạo học phần';
        byId('table-import-target-note').textContent = target === 'editor'
            ? 'Các thẻ sẽ được thêm vào cuối danh sách đang sửa.'
            : 'Tệp được đọc trên thiết bị này; nội dung không tải lên máy chủ.';
        if (target === 'new') byId('table-import-title').value = '';
        if (typeof closeAllModals === 'function') closeAllModals();
        byId('table-import-modal').style.display = 'flex';
        byId('table-import-file').focus();
    }

    function closeTableImporter() {
        byId('table-import-modal').style.display = 'none';
    }

    function setRows(nextRows, sourceName) {
        if (!Array.isArray(nextRows) || !nextRows.length) throw new Error('Không tìm thấy hàng dữ liệu trong tệp.');
        if (nextRows.length > MAX_ROWS) throw new Error(`Tệp có hơn ${MAX_ROWS.toLocaleString()} dòng; hãy chia nhỏ rồi nhập lại.`);
        const width = Math.max(...nextRows.map(row => Array.isArray(row) ? row.length : 0));
        if (!width) throw new Error('Không tìm thấy cột dữ liệu trong tệp.');
        if (width > 100) throw new Error('Tệp có hơn 100 cột; hãy chọn một vùng dữ liệu nhỏ hơn.');
        rows = nextRows.map(row => Array.from({ length: width }, (_, index) => String(row?.[index] ?? '')));
        byId('table-import-source').textContent = `${sourceName} · ${rows.length.toLocaleString()} dòng · ${width} cột`;
        const headerSelect = byId('table-import-header-row');
        const detectedHeader = guessHeaderRow(rows);
        headerSelect.replaceChildren(new Option('Không có tiêu đề', '0'));
        rows.slice(0, 20).forEach((_, index) => headerSelect.add(new Option(`Dòng ${index + 1}`, String(index + 1))));
        headerSelect.value = detectedHeader < 0 ? '0' : String(detectedHeader + 1);
        roles = guessRoles(getHeaders());
        render();
    }

    function getHeaders() {
        if (!rows.length) return [];
        const headerRow = Number(byId('table-import-header-row').value) - 1;
        return (headerRow >= 0 ? rows[headerRow] : rows[0].map((_, index) => `Cột ${index + 1}`))
            .map((value, index) => String(value || `Cột ${index + 1}`).trim());
    }

    function loadXlsx() {
        if (root.XLSX) return Promise.resolve(root.XLSX);
        if (xlsxPromise) return xlsxPromise;
        xlsxPromise = new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js';
            script.onload = () => root.XLSX ? resolve(root.XLSX) : reject(new Error('Không khởi tạo được bộ đọc Excel.'));
            script.onerror = () => reject(new Error('Không tải được bộ đọc Excel. Hãy kết nối Internet hoặc nhập CSV/TSV.'));
            document.head.append(script);
        }).catch(error => { xlsxPromise = null; throw error; });
        return xlsxPromise;
    }

    function loadSheet(index) {
        const name = workbook?.SheetNames[index];
        if (!name) return;
        const sheet = workbook.Sheets[name];
        setRows(root.XLSX.utils.sheet_to_json(sheet, { header: 1, defval: '', raw: false, blankrows: false }), name);
    }

    async function readFile(file) {
        clearSource();
        if (!file) return;
        if (file.size > MAX_FILE_BYTES) throw new Error('Tệp vượt quá 10 MB. Hãy chia nhỏ rồi nhập lại.');
        const extension = file.name.split('.').pop().toLowerCase();
        if (extension === 'xlsx') {
            byId('table-import-source').textContent = 'Đang đọc tệp Excel…';
            const XLSX = await loadXlsx();
            workbook = XLSX.read(await file.arrayBuffer(), { type: 'array', cellDates: true });
            const sheetSelect = byId('table-import-sheet');
            sheetSelect.replaceChildren(...workbook.SheetNames.map((name, index) => {
                const option = document.createElement('option');
                option.value = String(index); option.textContent = name; return option;
            }));
            byId('table-import-sheet-wrap').hidden = workbook.SheetNames.length < 2;
            loadSheet(0);
            return;
        }
        if (!['csv', 'tsv', 'txt'].includes(extension)) {
            throw new Error('Định dạng chưa hỗ trợ. Chọn .xlsx, .csv hoặc .tsv.');
        }
        const text = await file.text();
        textSource = { text, name: file.name, delimiter: extension === 'tsv' ? '\t' : 'auto', maxBytes: MAX_FILE_BYTES };
        parseSource();
    }

    function parseSource() {
        rows = [];
        roles = [];
        render();
        setError('');
        if (!textSource) return;
        byId('table-import-source').textContent = textSource.name;
        if (new Blob([textSource.text]).size > textSource.maxBytes) {
            throw new Error(`Dữ liệu vượt quá ${textSource.maxBytes / (1024 * 1024)} MB. Hãy chia nhỏ dữ liệu rồi nhập lại.`);
        }
        const selected = byId('table-import-delimiter').value;
        const delimiter = selected === 'custom' ? byId('table-import-delimiter-custom').value
            : selected === 'tab' ? '\t' : selected === 'auto' ? textSource.delimiter : selected;
        setRows(parseDelimited(textSource.text, delimiter).rows, textSource.name);
    }

    function renderColumnMap(headers) {
        const container = byId('table-import-column-map');
        container.replaceChildren();
        headers.forEach((header, index) => {
            const label = document.createElement('label');
            label.className = 'table-import-map-row';
            const name = document.createElement('span');
            name.textContent = header || `Cột ${index + 1}`;
            const select = document.createElement('select');
            select.className = 'q-input table-import-role';
            select.dataset.column = String(index);
            for (const [value, text] of [
                ['ignore', 'Bỏ qua'], ['term', 'Thuật ngữ'], ['definition', 'Định nghĩa'],
                ['term-extra', 'Ghép vào thuật ngữ'], ['definition-extra', 'Ghép vào định nghĩa']
            ]) {
                const option = document.createElement('option');
                option.value = value; option.textContent = text; select.append(option);
            }
            select.value = roles[index] || 'ignore';
            select.addEventListener('change', () => {
                roles[index] = select.value;
                renderPreview(headers);
            });
            label.append(name, select);
            container.append(label);
        });
    }

    function renderPreview(headers) {
        const result = mapRows(rows, Number(byId('table-import-header-row').value) - 1, roles);
        const preview = byId('table-import-preview');
        preview.replaceChildren();
        byId('table-import-count').textContent = String(result.cards.length);
        const summary = byId('table-import-summary');
        summary.textContent = result.invalidRows.length
            ? `Có ${result.invalidRows.length} dòng thiếu dữ liệu (${result.invalidRows.slice(0, 8).map(item => item.row).join(', ')}${result.invalidRows.length > 8 ? ', …' : ''}). Sửa cách ghép cột hoặc dữ liệu trước khi nhập.`
            : result.cards.length ? `${result.cards.length.toLocaleString()} thẻ hợp lệ.` : 'Chưa có thẻ hợp lệ để nhập.';
        summary.classList.toggle('table-import-warning', result.invalidRows.length > 0);
        const table = document.createElement('table');
        table.className = 'table-import-preview-grid';
        const head = table.createTHead().insertRow();
        ['Thuật ngữ', 'Định nghĩa'].forEach(value => { const th = document.createElement('th'); th.textContent = value; head.append(th); });
        const body = table.createTBody();
        result.cards.slice(0, 8).forEach(card => {
            const row = body.insertRow();
            [card.term, card.definition].forEach(value => { const cell = row.insertCell(); cell.textContent = value; });
        });
        preview.append(table);
        byId('table-import-submit').disabled = !result.cards.length || result.invalidRows.length > 0;
        return result;
    }

    function render() {
        const structured = rows.length > 0 && !textSource;
        byId('table-import-delimiter').disabled = structured;
        byId('table-import-delimiter-custom').hidden = byId('table-import-delimiter').value !== 'custom';
        byId('table-import-delimiter-custom').disabled = structured;
        const headers = getHeaders();
        byId('table-import-mapping-wrap').hidden = !rows.length;
        if (!rows.length) {
            byId('table-import-column-map').replaceChildren();
            byId('table-import-preview').replaceChildren();
            byId('table-import-count').textContent = '0';
            byId('table-import-summary').textContent = 'Chọn tệp hoặc dán bảng để xem trước.';
            byId('table-import-submit').disabled = true;
            return;
        }
        if (roles.length !== headers.length) roles = guessRoles(headers);
        renderColumnMap(headers);
        renderPreview(headers);
    }

    function handlePaste(event) {
        const html = event.clipboardData?.getData('text/html');
        if (!html || !/<table[\s>]/i.test(html)) return;
        const parsed = new DOMParser().parseFromString(html, 'text/html');
        const tableRows = [...parsed.querySelectorAll('table tr')].map(row =>
            [...row.querySelectorAll('th,td')].map(cell => cell.textContent.trim()));
        if (!tableRows.length) return;
        event.preventDefault();
        clearSource();
        setRows(tableRows, 'Bảng đã dán');
    }

    function appendToEditor(cards) {
        const list = byId('create-cards-list');
        const existing = [...list.querySelectorAll('.card-row')];
        const isEmpty = existing.every(row => !row.querySelector('.term-input').value.trim() &&
            !row.querySelector('.def-input').value.trim() && !row.querySelector('.image-input')?.value.trim());
        if (isEmpty) list.replaceChildren();
        cards.forEach(card => addCardRow(card.term, card.definition));
        reindexCardRows();
        if (window.saveEditorDraft) saveEditorDraft();
    }

    async function submit() {
        const result = renderPreview(getHeaders());
        if (!result.cards.length || result.invalidRows.length) return;
        const button = byId('table-import-submit');
        button.disabled = true;
        try {
            if (target === 'editor') {
                appendToEditor(result.cards);
                closeTableImporter();
                showToast(`Đã thêm ${result.cards.length} thẻ vào bản nháp.`);
                return;
            }
            const title = byId('table-import-title').value.trim() || `Học phần mới (${result.cards.length} thẻ)`;
            const set = {
                id: `set_${crypto.randomUUID()}`, title, description: '', numTerms: result.cards.length,
                cards: result.cards.map(card => ({ id: crypto.randomUUID(), term: card.term, definition: card.definition, image: '' }))
            };
            await saveCustomSet(set);
            closeTableImporter();
            await loadSetsList(set.id);
            showToast(`Đã tạo "${title}" với ${result.cards.length} thẻ.`);
        } catch (error) {
            setError(`Không nhập được dữ liệu: ${error.message}`);
        } finally {
            button.disabled = false;
        }
    }

    byId('table-import-file').addEventListener('change', async event => {
        try { await readFile(event.target.files?.[0]); setError(''); }
        catch (error) { setError(error.message); }
    });
    byId('table-import-sheet').addEventListener('change', event => loadSheet(Number(event.target.value)));
    byId('table-import-text').addEventListener('input', event => {
        const text = event.target.value;
        workbook = null;
        byId('table-import-file').value = '';
        byId('table-import-sheet').replaceChildren();
        byId('table-import-sheet-wrap').hidden = true;
        if (!text.trim()) { clearSource(); return; }
        textSource = { text, name: 'Văn bản đã dán', delimiter: 'auto', maxBytes: MAX_TEXT_BYTES };
        try {
            parseSource();
        } catch (error) { setError(error.message); }
    });
    for (const [id, event] of [['table-import-delimiter', 'change'], ['table-import-delimiter-custom', 'input']]) {
        byId(id).addEventListener(event, () => {
            try { parseSource(); }
            catch (error) { setError(error.message); }
        });
    }
    byId('table-import-text').addEventListener('paste', handlePaste);
    byId('table-import-header-row').addEventListener('change', () => {
        roles = guessRoles(getHeaders());
        render();
    });
    byId('table-import-submit').addEventListener('click', submit);
    byId('table-import-close').addEventListener('click', closeTableImporter);
    byId('table-import-cancel').addEventListener('click', closeTableImporter);
    byId('table-import-quizlet').addEventListener('click', () => {
        closeTableImporter();
        openQuickImportModal('link');
    });
    byId('table-import-clear').addEventListener('click', clearSource);
    byId('table-import-modal').addEventListener('click', event => {
        if (event.target === byId('table-import-modal')) closeTableImporter();
    });

    root.openTableImporter = openTableImporter;
    root.closeTableImporter = closeTableImporter;
})(typeof window === 'undefined' ? globalThis : window);
