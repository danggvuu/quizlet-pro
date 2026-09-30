import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

css_patch = """
    /* IMPORT FROM WORD/EXCEL UI */
    .import-btn-inline { background: transparent; color: var(--primary); border: 2px solid var(--primary); font-size: 14px; font-weight: 700; padding: 8px 16px; border-radius: 8px; cursor: pointer; transition: all 0.2s; margin-bottom: 20px;}
    .import-btn-inline:hover { background: var(--primary-light); }
    
    .import-box { background: var(--card-bg); border-radius: 12px; padding: 24px; margin-bottom: 30px; box-shadow: 0 4px 16px rgba(0,0,0,0.1); border: 1px solid var(--border); display: none; }
    .import-box-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; font-weight: 700; }
    .import-textarea { width: 100%; height: 120px; background: transparent; border: 2px solid var(--border); border-radius: 8px; padding: 12px; color: var(--text); font-family: monospace; resize: vertical; margin-bottom: 24px; outline: none; transition: border-color 0.2s;}
    .import-textarea:focus { border-color: var(--primary); }
    
    .import-settings { display: flex; gap: 40px; margin-bottom: 24px; }
    .import-setting-col { flex: 1; display: flex; flex-direction: column; gap: 12px; }
    .import-setting-title { font-size: 14px; font-weight: 800; }
    .radio-group { display: flex; align-items: center; gap: 8px; font-size: 14px; cursor: pointer; }
    .custom-sep-input { background: transparent; border: 1px solid var(--border); border-radius: 6px; padding: 6px 12px; color: var(--text); width: 120px; outline: none; }
    
    .import-preview { margin-bottom: 24px; }
    .import-preview-title { font-size: 16px; font-weight: 800; margin-bottom: 8px; }
    .import-preview-list { max-height: 200px; overflow-y: auto; background: var(--bg); border-radius: 8px; padding: 12px; border: 1px solid var(--border); }
    .preview-item { display: flex; gap: 16px; padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 14px; }
    .preview-item:last-child { border-bottom: none; }
    .preview-term { flex: 1; font-weight: 700; }
    .preview-def { flex: 1; color: var(--text-muted); }
    
    .import-actions { display: flex; justify-content: flex-end; gap: 12px; }
    .btn-cancel { background: transparent; color: var(--text); font-weight: 700; padding: 10px 20px; border-radius: 8px; border: none; cursor: pointer; }
    .btn-cancel:hover { background: var(--bg); }
"""

html_patch = """
    <input type="text" id="create-desc" class="q-input" placeholder="Thêm mô tả..." style="font-size: 16px; border: none; border-bottom: 2px solid var(--border); border-radius: 0; padding: 10px 0; margin-bottom: 20px; box-shadow: none;">

    <button class="import-btn-inline" onclick="document.getElementById('import-box-ui').style.display='block'">+ Nhập từ Word, Excel, Google Docs, v.v.</button>

    <div id="import-box-ui" class="import-box">
      <div class="import-box-header">
        <span>Nhập dữ liệu. Chép và dán dữ liệu ở đây</span>
        <button class="btn-icon" onclick="document.getElementById('import-box-ui').style.display='none'">✕</button>
      </div>
      <textarea id="import-raw-text" class="import-textarea" placeholder="Từ 1\tĐịnh nghĩa 1\nTừ 2\tĐịnh nghĩa 2" oninput="updateImportPreview()"></textarea>
      
      <div class="import-settings">
        <div class="import-setting-col">
          <div class="import-setting-title">Giữa thuật ngữ và định nghĩa</div>
          <label class="radio-group"><input type="radio" name="termSep" value="tab" checked onchange="updateImportPreview()"> Tab</label>
          <label class="radio-group"><input type="radio" name="termSep" value="comma" onchange="updateImportPreview()"> Phẩy</label>
          <label class="radio-group"><input type="radio" name="termSep" value="custom" onchange="updateImportPreview()"> 
            <input type="text" id="termSepCustom" class="custom-sep-input" placeholder="Tùy chỉnh" oninput="document.querySelector('input[name=termSep][value=custom]').checked=true; updateImportPreview()">
          </label>
        </div>
        <div class="import-setting-col">
          <div class="import-setting-title">Giữa các thẻ</div>
          <label class="radio-group"><input type="radio" name="cardSep" value="newline" checked onchange="updateImportPreview()"> Dòng mới</label>
          <label class="radio-group"><input type="radio" name="cardSep" value="semicolon" onchange="updateImportPreview()"> Chấm phẩy</label>
          <label class="radio-group"><input type="radio" name="cardSep" value="custom" onchange="updateImportPreview()"> 
            <input type="text" id="cardSepCustom" class="custom-sep-input" placeholder="Tùy chỉnh" oninput="document.querySelector('input[name=cardSep][value=custom]').checked=true; updateImportPreview()">
          </label>
        </div>
      </div>

      <div class="import-preview">
        <div class="import-preview-title">Xem trước (<span id="preview-count">0</span> thẻ)</div>
        <div id="preview-list" class="import-preview-list">Không có nội dung để xem trước</div>
      </div>

      <div class="import-actions">
        <button class="btn-cancel" onclick="document.getElementById('import-box-ui').style.display='none'">Hủy nhập</button>
        <button class="btn-primary" style="width: auto; padding: 10px 24px; font-size: 14px;" onclick="applyImportToRows()">Nhập</button>
      </div>
    </div>
"""

js_patch = """
    let parsedImportCards = [];

    function updateImportPreview() {
      const text = document.getElementById('import-raw-text').value;
      if (!text.trim()) {
        document.getElementById('preview-list').innerHTML = "Không có nội dung để xem trước";
        document.getElementById('preview-count').innerText = "0";
        parsedImportCards = [];
        return;
      }

      // Determine separators
      let termSep = document.querySelector('input[name="termSep"]:checked').value;
      if (termSep === 'tab') termSep = '\\t';
      else if (termSep === 'comma') termSep = ',';
      else termSep = document.getElementById('termSepCustom').value || '-'; // Default fallback

      let cardSep = document.querySelector('input[name="cardSep"]:checked').value;
      if (cardSep === 'newline') cardSep = '\\n';
      else if (cardSep === 'semicolon') cardSep = ';';
      else cardSep = document.getElementById('cardSepCustom').value || '\\n\\n';

      const cards = text.split(new RegExp(cardSep.replace(/([.*+?^=!:${}()|\[\]\/\\])/g, "\\$1")));
      parsedImportCards = [];
      let html = '';

      cards.forEach(c => {
        if (!c.trim()) return;
        const parts = c.split(new RegExp(termSep.replace(/([.*+?^=!:${}()|\[\]\/\\])/g, "\\$1")));
        const term = parts[0] ? parts[0].trim() : '';
        const def = parts.slice(1).join(termSep).trim();
        if (term || def) {
          parsedImportCards.push({ term, def });
          html += `<div class="preview-item"><div class="preview-term">${term}</div><div class="preview-def">${def}</div></div>`;
        }
      });

      document.getElementById('preview-list').innerHTML = html;
      document.getElementById('preview-count').innerText = parsedImportCards.length;
    }

    function applyImportToRows() {
      if (parsedImportCards.length === 0) return;
      
      // Clear existing empty rows if it's a fresh creation
      const list = document.getElementById('create-cards-list');
      const rows = document.querySelectorAll('.card-row');
      let isEmpty = true;
      rows.forEach(r => {
        if (r.querySelector('.term-input').value.trim() || r.querySelector('.def-input').value.trim()) isEmpty = false;
      });
      if (isEmpty) list.innerHTML = ''; // clear all empty default rows

      parsedImportCards.forEach(c => {
        addCardRow(c.term, c.def);
      });

      document.getElementById('import-box-ui').style.display = 'none';
      document.getElementById('import-raw-text').value = '';
      updateImportPreview();
    }
"""

if "IMPORT FROM WORD" not in content:
    content = content.replace("/* CREATE SET VIEW */", css_patch + "\n    /* CREATE SET VIEW */")
    content = content.replace('<div id="create-cards-list"></div>', html_patch + '\n    <div id="create-cards-list"></div>')
    content = content.replace("function addCardRow(term = '', definition = '') {", js_patch + "\n    function addCardRow(term = '', definition = '') {")

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched advanced import UI successfully.")
