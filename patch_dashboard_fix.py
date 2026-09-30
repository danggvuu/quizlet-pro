import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add the JS functions correctly just before </script>
js_code = """
    function showDashboard() {
      document.getElementById('study-view').style.display = 'none';
      document.getElementById('dashboard-view').style.display = 'block';
    }
    
    function renderDashboard(sets) {
      const view = document.getElementById('dashboard-view');
      if (!sets || sets.length === 0) return;
      
      const firstSet = sets[0];
      const restSets = sets.slice(1);
      
      let html = `
        <h2 class="section-title" style="margin-top: 0;">Jump back in</h2>
        <div class="jump-back-card" onclick="document.getElementById('set-select').value='${firstSet.id}'; onSetChange('${firstSet.id}')">
          <div class="jump-info">
            <h3>${firstSet.title}</h3>
            <p>${firstSet.numTerms} cards completed</p>
            <button class="btn-primary" style="width: auto; padding: 10px 24px; margin-top: 24px;">Continue</button>
          </div>
        </div>
      `;
      
      if (restSets.length > 0) {
        html += `<h2 class="section-title">Recents</h2><div class="grid-recents">`;
        restSets.forEach(s => {
          html += `
            <div class="set-card" onclick="document.getElementById('set-select').value='${s.id}'; onSetChange('${s.id}')">
              <div class="set-card-icon">🗂️</div>
              <div class="set-card-info">
                <div class="set-card-title">${s.title}</div>
                <div class="set-card-meta">${s.numTerms} cards ${s.isCustom ? '· by you' : ''}</div>
              </div>
            </div>
          `;
        });
        html += `</div>`;
      }
      view.innerHTML = html;
    }
"""

# check if it already exists to avoid duplicates
if "function renderDashboard" not in content:
    content = content.replace("</script>\n</body>", js_code + "\n  </script>\n</body>")

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed JS missing functions.")
else:
    print("Already exists.")

