import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add CSS
css_patch = """
    /* CREATE SET VIEW */
    .create-set-container { padding: 40px 24px; max-width: 1000px; width: 100%; margin: 0 auto; flex: 1; }
    .create-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px; }
    .card-row { background: var(--card-bg); border-radius: 12px; padding: 16px 24px; margin-bottom: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    .card-row-header { display: flex; justify-content: space-between; border-bottom: 1px solid var(--border); padding-bottom: 12px; margin-bottom: 16px; color: var(--text-muted); font-weight: 700; font-size: 14px;}
    .card-row-inputs { display: flex; gap: 24px; }
    .card-row-input-group { flex: 1; display: flex; flex-direction: column; }
    .card-row-input { border: none; border-bottom: 2px solid var(--text); background: transparent; color: var(--text); font-size: 16px; padding: 8px 0; outline: none; transition: border-color 0.2s; }
    .card-row-input:focus { border-bottom-color: var(--primary); }
    .card-row-label { font-size: 12px; font-weight: 700; color: var(--text-muted); margin-top: 8px; text-transform: uppercase; letter-spacing: 1px; }
    .add-card-btn { background: var(--card-bg); border: 2px dashed var(--border); color: var(--text); font-size: 16px; font-weight: 800; width: 100%; padding: 32px; border-radius: 12px; cursor: pointer; transition: all 0.2s; text-align: center; margin-bottom: 60px; }
    .add-card-btn:hover { background: var(--primary-light); color: var(--primary); border-color: var(--primary); }
"""
if "CREATE SET VIEW" not in content:
    content = content.replace("</style>", css_patch + "\n</style>")

# 2. Add HTML
html_patch = """
  <!-- CREATE SET VIEW -->
  <div id="create-set-view" class="create-set-container" style="display: none;">
    <div class="create-header">
      <h2 class="section-title" style="margin:0;">Tạo học phần mới</h2>
      <button class="btn-primary" style="width: auto; padding: 12px 32px;" onclick="saveCreatedSet()">Tạo</button>
    </div>
    
    <input type="text" id="create-title" class="q-input" placeholder="Nhập tiêu đề, ví dụ: Sinh học - Chương 22: Tiến hóa" style="font-size: 20px; font-weight: 800; border: none; border-bottom: 2px solid var(--text); border-radius: 0; padding: 10px 0; margin-bottom: 30px; box-shadow: none;">
    
    <div id="create-cards-list"></div>

    <button class="add-card-btn" onclick="addCardRow()">+ Thêm thẻ</button>
  </div>
"""
if "create-set-view" not in content:
    content = content.replace('<div id="dashboard-view"', html_patch + '\n  <div id="dashboard-view"')

# 3. Update the "+" button in Header
# Find <button class="btn-icon" id="btn-manual-import" title="Nhập thủ công thẻ mới" onclick="toggleManualModal()">➕</button>
header_btn_search = '<button class="btn-icon" id="btn-manual-import" title="Nhập thủ công thẻ mới" onclick="toggleManualModal()">➕</button>'
header_btn_replace = '<button class="btn-icon" id="btn-create-set" title="Tạo học phần mới" onclick="showCreateSetView()">➕</button>\n      <button class="btn-icon" id="btn-manual-import" title="Nhập thẻ dạng Text (Import)" onclick="toggleManualModal()">📄</button>'
content = content.replace(header_btn_search, header_btn_replace)

# 4. Add JS Functions
js_patch = """
    // ==========================================
    // CREATE SET VIEW LOGIC
    // ==========================================
    let createCardCounter = 0;

    function showCreateSetView() {
      document.getElementById('dashboard-view').style.display = 'none';
      document.getElementById('study-view').style.display = 'none';
      document.getElementById('create-set-view').style.display = 'block';
      
      document.getElementById('create-title').value = '';
      document.getElementById('create-cards-list').innerHTML = '';
      createCardCounter = 0;
      
      // Add 5 default empty rows
      for(let i=0; i<5; i++) addCardRow();
    }

    function addCardRow(term = '', definition = '') {
      createCardCounter++;
      const list = document.getElementById('create-cards-list');
      const div = document.createElement('div');
      div.className = 'card-row';
      div.id = `card-row-${createCardCounter}`;
      div.innerHTML = `
        <div class="card-row-header">
          <span>${createCardCounter}</span>
          <button class="btn-icon" style="width:28px; height:28px; font-size:12px;" onclick="document.getElementById('${div.id}').remove()" title="Xóa thẻ">🗑️</button>
        </div>
        <div class="card-row-inputs">
          <div class="card-row-input-group">
            <input type="text" class="card-row-input term-input" placeholder="Nhập thuật ngữ" value="${term}">
            <span class="card-row-label">Thuật ngữ</span>
          </div>
          <div class="card-row-input-group">
            <input type="text" class="card-row-input def-input" placeholder="Nhập định nghĩa" value="${definition}">
            <span class="card-row-label">Định nghĩa</span>
          </div>
        </div>
      `;
      list.appendChild(div);
      return div;
    }

    async function saveCreatedSet() {
      const title = document.getElementById('create-title').value.trim() || 'Học phần không tên';
      const rows = document.querySelectorAll('.card-row');
      const cards = [];
      
      rows.forEach((row, idx) => {
        const term = row.querySelector('.term-input').value.trim();
        const def = row.querySelector('.def-input').value.trim();
        if (term || def) {
          cards.push({ id: Date.now() + idx, term: term, definition: def, image: "" });
        }
      });
      
      if (cards.length === 0) {
        alert("Bạn phải nhập ít nhất 1 thẻ để tạo học phần!");
        return;
      }

      const newSet = {
        id: "set_" + Date.now(),
        title: title,
        numTerms: cards.length,
        cards: cards,
        isCustom: true
      };

      await window.Database.saveSet(newSet);
      showToast(`🎉 Đã tạo học phần: "${title}" (${cards.length} thẻ)!`, 4000);
      
      document.getElementById('create-set-view').style.display = 'none';
      await loadSetsList(newSet.id);
    }
"""

if "function showCreateSetView()" not in content:
    content = content.replace("function showDashboard() {", js_patch + "\n    function showDashboard() {")
    content = content.replace("document.getElementById('study-view').style.display = 'none';", "document.getElementById('study-view').style.display = 'none';\n      const csView = document.getElementById('create-set-view'); if(csView) csView.style.display = 'none';")

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched create set UI successfully.")
