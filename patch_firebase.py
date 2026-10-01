import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add Firebase SDKs in the head
firebase_sdks = """  <!-- FIREBASE SDK -->
  <script type="module">
    import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.1/firebase-app.js";
    import { getFirestore, collection, doc, setDoc, getDocs, deleteDoc, getDoc } from "https://www.gstatic.com/firebasejs/10.13.1/firebase-firestore.js";

    // 🔴 ÔNG DÁN FIREBASE CONFIG CỦA ÔNG VÀO ĐÂY NHÉ:
    const firebaseConfig = {
      apiKey: "CHUA_CO_KEY",
      authDomain: "CHUA_CO_KEY",
      projectId: "CHUA_CO_KEY",
      storageBucket: "CHUA_CO_KEY",
      messagingSenderId: "CHUA_CO_KEY",
      appId: "CHUA_CO_KEY"
    };

    let db;
    try {
      if (firebaseConfig.apiKey !== "CHUA_CO_KEY") {
        const app = initializeApp(firebaseConfig);
        db = getFirestore(app);
        window.FirebaseDB = db;
        console.log("Firebase Connected!");
      }
    } catch(e) { console.error("Firebase init error:", e); }

    // Cloud Database Wrapper
    window.CloudDB = {
      async saveSet(setObj) {
        if (!window.FirebaseDB) return false;
        try {
          await setDoc(doc(window.FirebaseDB, "quizlet_sets", String(setObj.id)), setObj);
          return true;
        } catch(e) { console.error(e); return false; }
      },
      async getAllSets() {
        if (!window.FirebaseDB) return [];
        try {
          const querySnapshot = await getDocs(collection(window.FirebaseDB, "quizlet_sets"));
          const sets = [];
          querySnapshot.forEach((doc) => {
            sets.push(doc.data());
          });
          return sets;
        } catch(e) { console.error(e); return []; }
      },
      async deleteSet(setId) {
        if (!window.FirebaseDB) return false;
        try {
          await deleteDoc(doc(window.FirebaseDB, "quizlet_sets", String(setId)));
          return true;
        } catch(e) { console.error(e); return false; }
      }
    };
  </script>
"""

search_head = "</head>"
if "firebasejs" not in content:
    content = content.replace(search_head, firebase_sdks + "\n</head>")

# Update Database methods to sync with CloudDB
search_db_save = """    async function saveCustomSet(setObj) {
      setObj.isCustom = true;
      if (!setObj.cards) setObj.cards = [];
      setObj.numTerms = setObj.cards.length;
      await window.Database.saveSet(setObj);
    }"""

replace_db_save = """    async function saveCustomSet(setObj) {
      setObj.isCustom = true;
      if (!setObj.cards) setObj.cards = [];
      setObj.numTerms = setObj.cards.length;
      
      // Save locally first
      await window.Database.saveSet(setObj);
      
      // Sync to Cloud if Firebase is ready
      if (window.CloudDB && window.FirebaseDB) {
        await window.CloudDB.saveSet(setObj);
      }
    }"""
content = content.replace(search_db_save, replace_db_save)

search_db_load = """      // 2. Custom sets from browser IndexedDB
      let dbSets = await window.Database.getAllSets() || [];"""

replace_db_load = """      // 2. Custom sets from Local DB & Cloud DB
      let dbSets = await window.Database.getAllSets() || [];
      if (window.CloudDB && window.FirebaseDB) {
         try {
           const cloudSets = await window.CloudDB.getAllSets();
           // Merge cloud sets with local sets
           cloudSets.forEach(cs => {
             if (!dbSets.some(ls => String(ls.id) === String(cs.id))) {
               dbSets.push(cs);
               // Cache locally
               window.Database.saveSet(cs);
             }
           });
         } catch(e) {}
      }"""
content = content.replace(search_db_load, replace_db_load)

search_db_delete = """    async function deleteCurrentSet() {
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

replace_db_delete = """    async function deleteCurrentSet() {
      if (!currentSet) return;
      let isCustom = currentSet.isCustom || String(currentSet.id).startsWith("set_") || String(currentSet.id).startsWith("custom_") || String(currentSet.id).startsWith("quizlet_");
      if (!isCustom) {
        alert("Bộ đề mẫu mặc định không thể xóa!");
        return;
      }
      if (confirm(`Bạn có chắc chắn muốn xóa vĩnh viễn bộ thẻ "${currentSet.title}" không?`)) {
        try {
          // Xóa Local
          await window.Database.deleteSet(currentSet.id);
          // Xóa Cloud
          if (window.CloudDB && window.FirebaseDB) {
            await window.CloudDB.deleteSet(currentSet.id);
          }
          showToast(`Đã xóa bộ thẻ "${currentSet.title}"!`, 3000);
          await loadSetsList();
        } catch(e) {
          console.error(e);
        }
      }
    }"""
content = content.replace(search_db_delete, replace_db_delete)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Injected Firebase logic.")
