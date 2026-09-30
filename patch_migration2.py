import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update saveCustomSet (since patch_migration.py might have failed earlier or I didn't verify it)
search_save = """    function saveCustomSet(setObj) {
      try {
        const sets = getStoredCustomSets().filter(s => String(s.id) !== String(setObj.id));
        sets.unshift(setObj);
        localStorage.setItem("qp_custom_sets", JSON.stringify(sets));
      } catch (e) {}
    }"""

replace_save = """    async function saveCustomSet(setObj) {
      setObj.isCustom = true;
      if (!setObj.cards) setObj.cards = [];
      setObj.numTerms = setObj.cards.length;
      await window.Database.saveSet(setObj);
    }
    
    async function migrateLocalStorageToIndexedDB() {
      if (localStorage.getItem("qp_migrated_v2")) return;
      const oldSets = getStoredCustomSets();
      if (oldSets && oldSets.length > 0) {
        for (const set of oldSets) {
          await saveCustomSet(set);
          // Migrate progress if exists
          try {
             const progRaw = localStorage.getItem(`qp_progress_${set.id}`);
             if (progRaw) {
               const map = JSON.parse(progRaw);
               for (const [cardId, p] of Object.entries(map)) {
                  let box = 0;
                  if (p.mastery === 1) box = 1;
                  if (p.mastery === 2) box = 3;
                  await window.Database.updateCardProgress(set.id, cardId, p.mastery > 0, p.starred);
               }
             }
          } catch(e) {}
        }
      }
      localStorage.setItem("qp_migrated_v2", "true");
    }"""
content = content.replace(search_save, replace_save)


# 2. Update deleteCurrentSet to use IndexedDB
search_delete = """    function deleteCurrentSet() {
      if (!currentSet) return;
      let isCustom = currentSet.isCustom || String(currentSet.id).startsWith("set_");
      if (!isCustom) {
        alert("Bộ đề mẫu mặc định không thể xóa!");
        return;
      }
      if (confirm(`Bạn có chắc chắn muốn xóa bộ thẻ "${currentSet.title}" khỏi trình duyệt không?`)) {
        try {
          const sets = getStoredCustomSets().filter(s => String(s.id) !== String(currentSet.id));
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
      let isCustom = currentSet.isCustom || String(currentSet.id).startsWith("set_");
      if (!isCustom) {
        alert("Bộ đề mẫu mặc định không thể xóa!");
        return;
      }
      if (confirm(`Bạn có chắc chắn muốn xóa bộ thẻ "${currentSet.title}" khỏi trình duyệt không?`)) {
        try {
          await window.Database.deleteSet(currentSet.id);
          showToast(`Đã xóa bộ thẻ "${currentSet.title}"!`, 3000);
          await loadSetsList();
        } catch(e) {
          console.error(e);
        }
      }
    }"""
content = content.replace(search_delete, replace_delete)


# 3. Inject migration into INIT
search_init = """    // INIT
    checkUrlHashImport();
    loadSetsList();"""

replace_init = """    // INIT
    (async () => {
      if (window.Database) {
        await window.Database.init();
        await migrateLocalStorageToIndexedDB();
      }
      await checkUrlHashImport();
      await loadSetsList();
    })();"""
content = content.replace(search_init, replace_init)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched DB migration and delete hooks successfully.")
