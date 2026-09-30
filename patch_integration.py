import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add <script src="js/database.js"></script> before the main script tag
content = content.replace('<script>', '<script src="js/database.js"></script>\n  <script>')

# 2. Replace getStoredCustomSets and saveCustomSet
search_storage = """    // STORAGE HELPERS
    function getStorageKey(setId) { return `qp_progress_${setId}`; }
    function loadProgressFromStorage(setId) {
      try {
        const raw = localStorage.getItem(getStorageKey(setId));
        return raw ? JSON.parse(raw) : {};
      } catch(e) { return {}; }
    }
    function saveProgressToStorage(setId, prog) {
      localStorage.setItem(getStorageKey(setId), JSON.stringify(prog));
    }
    function getStoredCustomSets() {
      try {
        const raw = localStorage.getItem("qp_custom_sets");
        return raw ? JSON.parse(raw) : [];
      } catch(e) { return []; }
    }
    function saveCustomSet(setObj) {
      let sets = getStoredCustomSets();
      const idx = sets.findIndex(s => s.id === setObj.id);
      if (idx > -1) {
        sets[idx] = setObj;
      } else {
        sets.push(setObj);
      }
      localStorage.setItem("qp_custom_sets", JSON.stringify(sets));
    }"""

replace_storage = """    // NEW STORAGE API VIA DATABASE.JS (INDEXEDDB)
    async function loadProgressFromStorage(setId) {
      // Wrapper để tương thích UI cũ (Sẽ gọi DB sau)
      return {};
    }
    async function saveProgressToStorage(setId, prog) {}
    
    async function saveCustomSet(setObj) {
      setObj.isCustom = true;
      if (!setObj.cards) setObj.cards = [];
      setObj.numTerms = setObj.cards.length;
      await window.Database.saveSet(setObj);
    }"""

content = content.replace(search_storage, replace_storage)

# 3. Modify loadSetsList to use Database
search_loadsets = """      // 2. Custom sets from browser localStorage
      const customSets = getStoredCustomSets().map(s => ({
        id: s.id,
        title: s.title,
        numTerms: s.cards ? s.cards.length : (s.numTerms || 0),
        isCustom: true
      }));"""

replace_loadsets = """      // 2. Custom sets from browser IndexedDB
      let dbSets = await window.Database.getAllSets() || [];
      const customSets = dbSets.map(s => ({
        id: s.id,
        title: s.title,
        numTerms: s.cards ? s.cards.length : (s.numTerms || 0),
        isCustom: true
      }));"""

content = content.replace(search_loadsets, replace_loadsets)

# 4. Modify loadSetData to fetch from DB first
search_loadsetdata = """    async function loadSetData(setId) {
      if (!setId) return;
      currentSet = null;

      // 1. Try finding in custom sets
      const customSets = getStoredCustomSets();
      const found = customSets.find(s => String(s.id) === String(setId));
      if (found) {
        currentSet = found;
        finishLoadSet();
        return;
      }"""

replace_loadsetdata = """    async function loadSetData(setId) {
      if (!setId) return;
      currentSet = null;

      // 1. Try finding in IndexedDB
      const found = await window.Database.getSetById(setId);
      if (found) {
        currentSet = found;
        finishLoadSet();
        return;
      }"""

content = content.replace(search_loadsetdata, replace_loadsetdata)

# 5. Modify deleteCurrentSet
search_delete = """    function deleteCurrentSet() {
      if (!currentSet) return;
      if (confirm(`Bạn có chắc muốn xóa bộ thẻ "${currentSet.title}" khỏi trình duyệt không?`)) {
        try {
          let sets = getStoredCustomSets();
          sets = sets.filter(s => s.id !== currentSet.id);
          localStorage.setItem("qp_custom_sets", JSON.stringify(sets));
          localStorage.removeItem(getStorageKey(currentSet.id));
          showToast(`Đã xóa bộ thẻ "${currentSet.title}"!`, 3000);
          loadSetsList();
        } catch(e) {
          console.error(e);
        }
      }
    }"""

replace_delete = """    async function deleteCurrentSet() {
      if (!currentSet) return;
      if (confirm(`Bạn có chắc muốn xóa bộ thẻ "${currentSet.title}" khỏi trình duyệt không?`)) {
        try {
          await window.Database.deleteSet(currentSet.id);
          showToast(`Đã xóa bộ thẻ "${currentSet.title}"!`, 3000);
          loadSetsList();
        } catch(e) {
          console.error(e);
        }
      }
    }"""

content = content.replace(search_delete, replace_delete)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched storage to IndexedDB successfully.")
