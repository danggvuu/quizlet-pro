import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace saveCustomSet
search_save = """    function getStoredCustomSets() {
      try {
        const raw = localStorage.getItem("qp_custom_sets");
        return raw ? JSON.parse(raw) : [];
      } catch (e) { return []; }
    }
    function saveCustomSet(setObj) {
      try {
        const sets = getStoredCustomSets().filter(s => String(s.id) !== String(setObj.id));
        sets.unshift(setObj);
        localStorage.setItem("qp_custom_sets", JSON.stringify(sets));
      } catch (e) {}
    }"""

replace_save = """    function getStoredCustomSets() {
      try {
        const raw = localStorage.getItem("qp_custom_sets");
        return raw ? JSON.parse(raw) : [];
      } catch (e) { return []; }
    }
    async function saveCustomSet(setObj) {
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
          // Also migrate progress if exists
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
    }
"""

content = content.replace(search_save, replace_save)

# Inject migration call into start() or document ready
search_init = """    // INIT APP
    window.onload = async () => {"""

replace_init = """    // INIT APP
    window.onload = async () => {
      if (window.Database) {
        await window.Database.init();
        await migrateLocalStorageToIndexedDB();
      }"""
content = content.replace(search_init, replace_init)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched DB migration successfully.")
