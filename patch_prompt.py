import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

search_prompt = """      let title = defaultTitle;
      if (!title) {
        const userPrompt = prompt(`Tìm thấy ${cards.length} từ vựng! Nhập tên cho bộ thẻ này:`, `Bộ thẻ mới (${cards.length} từ)`);
        title = (userPrompt && userPrompt.trim()) ? userPrompt.trim() : `Bộ thẻ mới (${cards.length} từ)`;
      }"""

replace_prompt = """      let title = defaultTitle;
      if (!title) {
        title = `Bộ thẻ mới (${cards.length} từ)`;
      }"""

content = content.replace(search_prompt, replace_prompt)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Removed native prompt.")
