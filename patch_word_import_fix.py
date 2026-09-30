import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

bad_js1 = r'const cards = text.split(new RegExp(cardSep.replace(/([.*+?^=!:${}()|\[\]\/\])/g, "\$1")));'
bad_js2 = r'const parts = c.split(new RegExp(termSep.replace(/([.*+?^=!:${}()|\[\]\/\])/g, "\$1")));'

good_js1 = r'const cards = text.split(new RegExp(cardSep.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));'
good_js2 = r'const parts = c.split(new RegExp(termSep.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));'

content = content.replace(bad_js1, good_js1)
content = content.replace(bad_js2, good_js2)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed JS regex escaping.")
