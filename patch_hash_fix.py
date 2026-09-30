import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

search_hash = """    function checkUrlHashImport() {
      if (window.location.hash.startsWith("#data=")) {
        try {
          const raw = decodeURIComponent(window.location.hash.substring(6));
          const imported = JSON.parse(raw);
          if (imported && imported.cards && imported.cards.length > 0) {
            saveCustomSet(imported);
            try {
              history.replaceState(null, null, window.location.pathname);
            } catch(e) {}
            loadSetsList(imported.id);"""

replace_hash = """    async function checkUrlHashImport() {
      if (window.location.hash.startsWith("#data=")) {
        try {
          const raw = decodeURIComponent(window.location.hash.substring(6));
          const imported = JSON.parse(raw);
          if (imported && imported.cards && imported.cards.length > 0) {
            await saveCustomSet(imported);
            try {
              history.replaceState(null, null, window.location.pathname);
            } catch(e) {}
            await loadSetsList(imported.id);"""
            
content = content.replace(search_hash, replace_hash)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched hash import successfully.")
