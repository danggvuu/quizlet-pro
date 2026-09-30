import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace STORAGE HELPERS
search_storage = """    // STORAGE HELPERS
    function getStorageKey(setId) { return `qp_progress_${setId}`; }
    function loadProgressFromStorage(setId) {
      try {
        const raw = localStorage.getItem(getStorageKey(setId));
        return raw ? JSON.parse(raw) : {};
      } catch (e) { return {}; }
    }
    function saveProgressToStorage() {
      if (!currentSet) return;
      try {
        const map = {};
        cardsState.forEach(c => { map[c.id] = { mastery: c.mastery, starred: c.starred }; });
        localStorage.setItem(getStorageKey(currentSet.id), JSON.stringify(map));
      } catch (e) {}
    }"""

replace_storage = """    // STORAGE HELPERS (DELEGATED TO DB)
    function getStorageKey(setId) { return `qp_progress_${setId}`; }
    async function loadProgressFromStorage(setId) {
      const progs = await window.Database.getProgress(setId);
      const map = {};
      progs.forEach(p => { map[p.cardId] = p; });
      return map;
    }
    function saveProgressToStorage() {
      if (!currentSet) return;
      cardsState.forEach(c => {
        // Map mastery back to box
        // Mastery: 0 = Unseen, 1 = Learning (Box 1 or 2), 2 = Mastered (Box 3)
        let box = 0;
        if (c.mastery === 1) box = 1;
        if (c.mastery === 2) box = 3;
        window.Database.updateCardProgress(currentSet.id, c.id, c.mastery > 0, c.starred);
      });
    }"""

content = content.replace(search_storage, replace_storage)

# Replace cardsState init in loadSetData
search_init = """        const savedProgress = loadProgressFromStorage(setId);
        cardsState = (setObj.cards || []).map((c, idx) => {
          const sv = savedProgress[c.id || idx] || {};
          return {
            id: c.id || idx,
            term: c.term || "",
            definition: c.definition || "",
            image: c.image || "",
            mastery: sv.mastery || 0,
            starred: !!sv.starred,
            incorrectCount: 0
          };
        });"""

replace_init = """        const savedProgress = await loadProgressFromStorage(setId);
        cardsState = (setObj.cards || []).map((c, idx) => {
          const sv = savedProgress[c.id || idx] || {};
          let m = 0;
          if (sv.box === 3) m = 2; // Mastered
          else if (sv.box === 1 || sv.box === 2) m = 1; // Learning
          
          return {
            id: c.id || idx,
            term: c.term || "",
            definition: c.definition || "",
            image: c.image || "",
            mastery: m,
            starred: !!sv.isStarred,
            incorrectCount: 0
          };
        });"""

content = content.replace(search_init, replace_init)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched storage helpers successfully.")
