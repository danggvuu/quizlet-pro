import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add export button to HTML
search_html = """      <button id="btn-del-set" class="btn-icon" style="display:none; width: 30px; height: 30px; font-size: 13px; border-color: var(--error); color: var(--error);" onclick="deleteCurrentSet()" title="Xóa bộ thẻ tự tạo này khỏi trình duyệt">🗑️</button>
    </div>"""

replace_html = """      <button id="btn-export-set" class="btn-icon" style="display:none; width: 30px; height: 30px; font-size: 13px; color: var(--primary); border-color: var(--primary);" onclick="exportCurrentSet()" title="Copy/Xuất bộ thẻ này">📤</button>
      <button id="btn-del-set" class="btn-icon" style="display:none; width: 30px; height: 30px; font-size: 13px; border-color: var(--error); color: var(--error);" onclick="deleteCurrentSet()" title="Xóa bộ thẻ tự tạo này khỏi trình duyệt">🗑️</button>
    </div>"""
content = content.replace(search_html, replace_html)

# Add logic to show the export button
search_show = """      if (isCustom) {
        document.getElementById("btn-del-set").style.display = "inline-flex";
      } else {
        document.getElementById("btn-del-set").style.display = "none";
      }"""

replace_show = """      if (isCustom) {
        document.getElementById("btn-del-set").style.display = "inline-flex";
        document.getElementById("btn-export-set").style.display = "inline-flex";
      } else {
        document.getElementById("btn-del-set").style.display = "none";
        document.getElementById("btn-export-set").style.display = "none";
      }"""
content = content.replace(search_show, replace_show)

# Add exportCurrentSet function
search_func = """    function deleteCurrentSet() {"""

replace_func = """    function exportCurrentSet() {
      if (!currentSet || !cardsState || cardsState.length === 0) return;
      let out = "";
      cardsState.forEach(c => {
         out += `${c.term} : ${c.definition}\n`;
      });
      navigator.clipboard.writeText(out).then(() => {
        showToast("✅ Đã copy toàn bộ từ vựng! Hãy gửi dán nó vào đâu đó.", 3000);
      });
    }

    function deleteCurrentSet() {"""
content = content.replace(search_func, replace_func)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added export feature.")
