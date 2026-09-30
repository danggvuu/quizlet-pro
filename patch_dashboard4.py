import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

search_str = """    function onSetChange(setId) {
      updateDeleteButtonVisibility();
      loadSetData(setId);
    }"""

replace_str = """    function onSetChange(setId) {
      document.getElementById('dashboard-view').style.display = 'none';
      document.getElementById('study-view').style.display = 'flex';
      updateDeleteButtonVisibility();
      loadSetData(setId);
    }"""

content = content.replace(search_str, replace_str)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched onSetChange successfully.")
