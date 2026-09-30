import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the end of loadSetsList
search_str = """      if (selectedId) select.value = selectedId;
      else if (allSets.length > 0) select.value = allSets[0].id;

      updateDeleteButtonVisibility();

      if (select.value) {
        loadSetData(select.value);
      }
    }"""

replace_str = """      renderDashboard(allSets);

      if (selectedId) {
        select.value = selectedId;
        updateDeleteButtonVisibility();
        loadSetData(select.value);
        document.getElementById('dashboard-view').style.display = 'none';
        document.getElementById('study-view').style.display = 'flex';
      } else {
        if (allSets.length > 0) select.value = allSets[0].id;
        updateDeleteButtonVisibility();
        showDashboard();
      }
    }"""

content = content.replace(search_str, replace_str)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched loadSetsList successfully.")
