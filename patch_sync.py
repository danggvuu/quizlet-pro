import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

search = """           cloudSets.forEach(cs => {
             if (!dbSets.some(ls => String(ls.id) === String(cs.id))) {
               dbSets.push(cs);
               // Cache locally
               window.Database.saveSet(cs);
             }
           });
         } catch(e) {}
      }"""

replace = """           cloudSets.forEach(cs => {
             if (!dbSets.some(ls => String(ls.id) === String(cs.id))) {
               dbSets.push(cs);
               // Cache locally
               window.Database.saveSet(cs);
             }
           });
           
           // AUTO-SYNC: Push any local sets that are MISSING in the cloud
           let syncedCount = 0;
           for (const ls of dbSets) {
             if (ls.isCustom && !cloudSets.some(cs => String(cs.id) === String(ls.id))) {
                await window.CloudDB.saveSet(ls);
                syncedCount++;
             }
           }
           if (syncedCount > 0) {
              console.log("Đã đồng bộ " + syncedCount + " bộ thẻ cũ lên Cloud!");
           }

         } catch(e) {}
      }"""

content = content.replace(search, replace)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Injected auto-sync logic.")
