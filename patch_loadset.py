import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

search_loadset = """    async function loadSetData(setId) {
      try {
        let setObj = null;

        // 1. Check custom sets in localStorage
        const custom = getStoredCustomSets().find(s => String(s.id) === String(setId));
        if (custom) {
          setObj = custom;
        } else {"""

replace_loadset = """    async function loadSetData(setId) {
      try {
        let setObj = null;

        // 1. Check custom sets in IndexedDB
        const custom = await window.Database.getSetById(setId);
        if (custom) {
          setObj = custom;
        } else {"""

content = content.replace(search_loadset, replace_loadset)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched loadSetData successfully.")
