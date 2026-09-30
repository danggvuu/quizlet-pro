import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

css_search = """    .modal-content {
      background: var(--card-bg);
      border-radius: var(--radius);
      max-width: 580px;
      width: 100%;
      max-height: 85vh;
      overflow-y: auto;
      padding: 28px;
      box-shadow: 0 16px 40px rgba(0,0,0,0.3);
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      font-size: 18px;
      font-weight: 800;
    }"""

css_replace = """    .modal-content {
      background: var(--card-bg);
      border-radius: 20px;
      max-width: 600px;
      width: 100%;
      max-height: 85vh;
      overflow-y: auto;
      padding: 32px;
      box-shadow: 0 16px 48px rgba(0,0,0,0.2);
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      font-size: 20px;
      font-weight: 800;
    }
    .modal-close-btn {
      background: var(--bg);
      border: none;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--text-muted);
      transition: all 0.2s;
      font-size: 18px;
      font-weight: bold;
    }
    .modal-close-btn:hover { background: var(--border); color: var(--text); }
    .q-input {
      width: 100%;
      padding: 14px 16px;
      border-radius: 12px;
      border: 2px solid var(--border);
      background: transparent;
      color: var(--text);
      font-size: 16px;
      font-weight: 700;
      transition: all 0.2s;
      outline: none;
    }
    .q-input:focus { border-color: var(--primary); }
    
    .q-textarea {
      width: 100%;
      padding: 16px;
      border-radius: 12px;
      border: 2px solid var(--border);
      background: transparent;
      color: var(--text);
      font-size: 15px;
      transition: all 0.2s;
      outline: none;
      resize: vertical;
    }
    .q-textarea:focus { border-color: var(--primary); }
    .q-label {
      font-size: 13px;
      color: var(--text-muted);
      display: block;
      margin-bottom: 8px;
      font-weight: 700;
    }"""
content = content.replace(css_search, css_replace)


html_search = """  <div id="manual-modal" class="modal-overlay" style="display: none;">
    <div class="modal-content">
      <div class="modal-header">
        <div>➕ Nhập thẻ thủ công (Paste Text)</div>
        <button class="btn-icon" onclick="toggleManualModal()">✕</button>
      </div>
      <div style="display: flex; flex-direction: column; gap: 14px;">
        <input type="text" id="manual-title" placeholder="Tên bộ thẻ (VD: Từ vựng TOEIC Part 7)" style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg); color: var(--text);">
        <div>
          <label style="font-size: 12px; color: var(--text-muted); display: block; margin-bottom: 4px;">Dán từ vựng vào đây (mỗi dòng 1 từ, ngăn cách bằng dấu gạch nối hoặc Tab):</label>
          <textarea id="manual-text" rows="8" placeholder="car - ô tô\nbook - cuốn sách\napple - quả táo" style="width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg); color: var(--text); font-family: monospace;"></textarea>
        </div>
        <button class="btn-continue" onclick="submitManualImport()">Lưu & Học ngay</button>
      </div>
    </div>
  </div>"""

html_replace = """  <div id="manual-modal" class="modal-overlay" style="display: none;">
    <div class="modal-content">
      <div class="modal-header">
        <div>✨ Nhập thẻ thủ công (Paste Text)</div>
        <button class="modal-close-btn" onclick="toggleManualModal()">✕</button>
      </div>
      <div style="display: flex; flex-direction: column; gap: 20px;">
        <div>
          <input type="text" id="manual-title" class="q-input" placeholder="Tên bộ thẻ (VD: Từ vựng TOEIC Part 7)">
        </div>
        <div>
          <label class="q-label">Dán từ vựng vào đây (mỗi dòng 1 từ, ngăn cách bằng dấu gạch nối hoặc Tab):</label>
          <textarea id="manual-text" class="q-textarea" rows="8" placeholder="car - ô tô\nbook - cuốn sách\napple - quả táo"></textarea>
        </div>
        <button class="btn-primary" style="padding: 16px; font-size: 16px; margin-top: 8px;" onclick="submitManualImport()">Lưu & Học ngay</button>
      </div>
    </div>
  </div>"""
content = content.replace(html_search, html_replace)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched modal HTML and CSS successfully.")
