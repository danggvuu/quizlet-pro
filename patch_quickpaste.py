import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

search_paste = """    async function pasteFromClipboard() {
      try {
        let text = "";
        if (navigator.clipboard && navigator.clipboard.readText) {
          text = await navigator.clipboard.readText();
        }
        if (!text || !text.trim()) {
          toggleManualModal();
          const tArea = document.getElementById("manual-text");
          if (tArea) {
            tArea.focus();
            tArea.placeholder = "Dán từ vựng từ Quizlet vào đây nhé...\nHoặc ấn Ctrl+V / Cmd+V";
          }
          return;
        }
        parseAndImportText(text, null);
      } catch (err) {
        console.error("Không thể tự động đọc Clipboard: ", err);
        toggleManualModal();
      }
    }"""

replace_paste = """    async function pasteFromClipboard() {
      try {
        let text = "";
        if (navigator.clipboard && navigator.clipboard.readText) {
          text = await navigator.clipboard.readText();
        }
        toggleManualModal();
        if (text && text.trim()) {
          document.getElementById("manual-text").value = text;
          document.getElementById("manual-title").focus();
        } else {
          const tArea = document.getElementById("manual-text");
          if (tArea) {
            tArea.focus();
            tArea.placeholder = "Dán từ vựng từ Quizlet vào đây nhé...\nHoặc ấn Ctrl+V / Cmd+V";
          }
        }
      } catch (err) {
        console.error("Không thể tự động đọc Clipboard: ", err);
        toggleManualModal();
      }
    }"""

content = content.replace(search_paste, replace_paste)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched pasteFromClipboard successfully.")
