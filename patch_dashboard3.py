import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the previous renderDashboard with a better one
search_str = """    function renderDashboard(sets) {
      const grid = document.getElementById('dashboard-grid');
      grid.innerHTML = '';
      sets.forEach(s => {
        const div = document.createElement('div');
        div.className = 'set-card';
        div.onclick = () => {
          document.getElementById('set-select').value = s.id;
          onSetChange(s.id);
        };
        div.innerHTML = `
          <div class="set-card-icon">🗂️</div>
          <div class="set-card-info">
            <div class="set-card-title">${s.title}</div>
            <div class="set-card-meta">${s.numTerms} cards ${s.isCustom ? '· by you' : ''}</div>
          </div>
        `;
        grid.appendChild(div);
      });
    }"""

replace_str = """    function renderDashboard(sets) {
      const view = document.getElementById('dashboard-view');
      if (sets.length === 0) return;
      
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
              <div class="set-card-icon">📱</div>
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
    }"""

css_search = """    .set-card-meta { font-size: 12px; font-weight: 700; color: var(--text-muted); }"""
css_replace = """    .set-card-meta { font-size: 12px; font-weight: 700; color: var(--text-muted); }
    .jump-back-card {
      background: linear-gradient(135deg, var(--card-bg) 0%, var(--primary-light) 100%);
      border: 2px solid var(--border);
      border-radius: 24px;
      padding: 40px;
      display: flex;
      cursor: pointer;
      transition: all 0.2s;
      margin-bottom: 40px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.06);
    }
    .jump-back-card:hover { transform: translateY(-4px); border-color: var(--primary); }
    .jump-back-card h3 { font-size: 28px; font-weight: 900; margin-bottom: 8px; }
    .jump-back-card p { font-size: 14px; font-weight: 700; color: var(--text-muted); }
"""

content = content.replace(search_str, replace_str)
content = content.replace(css_search, css_replace)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched renderDashboard successfully.")
