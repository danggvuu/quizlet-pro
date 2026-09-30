import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

search_retype_html = """      let retypeHtml = "";
      if (requireRetype) {
        retypeHtml = `
          <div class="retype-container">
            <div class="retype-label">✍️ Gõ lại câu trả lời đúng để tiếp tục:</div>
            <input type="text" id="retype-input" class="retype-input" placeholder="Gõ lại chính xác câu trả lời ở trên..." autocomplete="off" />
          </div>
        `;
      }"""

replace_retype_html = """      let retypeHtml = "";
      if (requireRetype) {
        retypeHtml = `
          <div class="retype-container">
            <div class="retype-label">✍️ Gõ lại câu trả lời đúng để tiếp tục (Hoặc ấn Enter để bỏ qua):</div>
            <input type="text" id="retype-input" class="retype-input" placeholder="Gõ chính xác, hoặc ấn Enter để bỏ qua..." autocomplete="off" />
          </div>
        `;
      }"""
content = content.replace(search_retype_html, replace_retype_html)

search_btn = """          <button class="btn-continue" id="btn-next-wrong" onclick="nextCardAfterFeedback()">
            ${requireRetype ? "Tiếp tục (hoặc gõ đúng)" : "Tiếp tục (Nhấn Space / Enter) →"}
          </button>"""

replace_btn = """          <button class="btn-continue" id="btn-next-wrong" onclick="nextCardAfterFeedback()">
            ${requireRetype ? "Bỏ qua & Tiếp tục (Enter)" : "Tiếp tục (Nhấn Space / Enter) →"}
          </button>"""
content = content.replace(search_btn, replace_btn)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched retype UI.")
