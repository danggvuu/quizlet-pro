import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Make parseAndImportText async
search_parse = """    function parseAndImportText(text, defaultTitle = null) {"""
replace_parse = """    async function parseAndImportText(text, defaultTitle = null) {"""
content = content.replace(search_parse, replace_parse)

search_parse_call1 = """          if (obj.cards && Array.isArray(obj.cards) && obj.cards.length > 0) {
            saveCustomSet(obj);
            closeAllModals();
            loadSetsList(obj.id);"""
replace_parse_call1 = """          if (obj.cards && Array.isArray(obj.cards) && obj.cards.length > 0) {
            await saveCustomSet(obj);
            closeAllModals();
            await loadSetsList(obj.id);"""
content = content.replace(search_parse_call1, replace_parse_call1)

search_parse_call2 = """      saveCustomSet(newSet);
      closeAllModals();
      loadSetsList(newSet.id);"""
replace_parse_call2 = """      await saveCustomSet(newSet);
      closeAllModals();
      await loadSetsList(newSet.id);"""
content = content.replace(search_parse_call2, replace_parse_call2)

search_submit = """      parseAndImportText(text, title);
      document.getElementById("manual-title").value = "";"""
replace_submit = """      await parseAndImportText(text, title);
      document.getElementById("manual-title").value = "";"""
content = content.replace(search_submit, replace_submit)


# Fix 2: Add "Tạo" button at the bottom of Create Set view
search_add_btn = """    <button class="add-card-btn" onclick="addCardRow()">+ Thêm thẻ</button>
  </div>"""

replace_add_btn = """    <button class="add-card-btn" onclick="addCardRow()">+ Thêm thẻ</button>
    <div style="display: flex; justify-content: flex-end; margin-top: 20px;">
      <button class="btn-primary" style="width: auto; padding: 16px 48px; font-size: 18px;" onclick="saveCreatedSet()">Tạo</button>
    </div>
  </div>"""
content = content.replace(search_add_btn, replace_add_btn)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched save issues successfully.")
