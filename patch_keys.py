import re

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

search_config = """    const firebaseConfig = {
      apiKey: "CHUA_CO_KEY",
      authDomain: "CHUA_CO_KEY",
      projectId: "CHUA_CO_KEY",
      storageBucket: "CHUA_CO_KEY",
      messagingSenderId: "CHUA_CO_KEY",
      appId: "CHUA_CO_KEY"
    };"""

replace_config = """    const firebaseConfig = {
      apiKey: "AIzaSyDQrqe_dx7jQAitQ9gmrcnY6_TNl2frON0",
      authDomain: "bhjbhj-c8bdd.firebaseapp.com",
      projectId: "bhjbhj-c8bdd",
      storageBucket: "bhjbhj-c8bdd.firebasestorage.app",
      messagingSenderId: "863761099968",
      appId: "1:863761099968:web:841abf121b6ceb18441125",
      measurementId: "G-QWZRQ35NG1"
    };"""

content = content.replace(search_config, replace_config)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Injected real Firebase Config.")
