import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

search_css = """    .btn-skip {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      padding: 8px 12px;
      border-radius: 8px;
    }
    .btn-skip:hover { background: var(--bg); color: var(--text); }"""

replace_css = """    .btn-skip {
      background: var(--bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      padding: 12px 24px;
      border-radius: 10px;
      transition: all 0.2s;
    }
    .btn-skip:hover { background: var(--border); color: var(--text); }"""
content = content.replace(search_css, replace_css)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched skip button CSS.")
