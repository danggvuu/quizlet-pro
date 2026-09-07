import http.server
import json
import os
import re
import urllib.parse
import urllib.request
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "sets"

class handler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/sets" or path == "/api/sets/":
            self.handle_list_sets()
            return
        elif path.startswith("/api/sets/"):
            set_id = path.replace("/api/sets/", "").strip()
            self.handle_get_set(set_id)
            return
        elif path.startswith("/api/tts"):
            self.handle_tts(parsed.query)
            return

        self.send_json({"status": "ok", "message": "Quizlet Pro API is running"}, 200)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

        if path == "/api/manual-import":
            try:
                payload = json.loads(body)
                title = payload.get("title", "Bộ thẻ tự tạo").strip() or "Bộ thẻ tự tạo"
                cards = payload.get("cards", [])
                set_id = payload.get("id") or f"custom_{int(time.time())}"
                set_obj = {
                    "id": set_id,
                    "title": title,
                    "description": payload.get("description", "Nhập thủ công"),
                    "numTerms": len(cards),
                    "cards": cards
                }
                self.send_json({"status": "ok", "set": set_obj})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)
            return

        elif path == "/api/scrape":
            # On Vercel cloud serverless, Cloudflare blocks datacenter IPs without local Chrome cookies
            self.send_json({
                "status": "error",
                "message": "Trên phiên bản web Vercel online, Quizlet chặn bot đám mây. Vui lòng bấm nút [➕ Nhập thủ công] (copy-paste từ nút Xuất của Quizlet) hoặc chạy app trên máy tính bằng file Chay_Quizlet_Pro.command để cào tự động nhé!"
            }, 200)
            return

        self.send_json({"status": "error", "message": "Not found"}, 404)

    def handle_tts(self, query_str):
        query = urllib.parse.parse_qs(query_str)
        text = query.get("q", [""])[0]
        lang = query.get("tl", ["en"])[0]
        if not text:
            self.send_response(400)
            self.end_headers()
            return
        clean_text = text.split("\n")[0]
        clean_text = re.sub(r"[\/\(\)=><\+]", " ", clean_text).strip()
        if "=" in clean_text:
            clean_text = clean_text.split("=")[0].strip()
        clean_text = clean_text[:120]

        tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl={lang}&q={urllib.parse.quote(clean_text)}"
        req = urllib.request.Request(tts_url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                audio_data = resp.read()
                self.send_response(200)
                self.send_header("Content-type", "audio/mpeg")
                self.send_header("Content-length", str(len(audio_data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(audio_data)
        except Exception as e:
            self.send_response(500)
            self.end_headers()

    def handle_list_sets(self):
        sets_list = []
        if DATA_DIR.exists():
            for p in DATA_DIR.glob("*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        d = json.load(f)
                        sets_list.append({
                            "id": d.get("id"),
                            "title": d.get("title", p.stem),
                            "numTerms": d.get("numTerms", len(d.get("cards", [])))
                        })
                except Exception:
                    pass
        # Đảm bảo luôn có ít nhất bộ Test 1
        if not any(str(s["id"]) == "927731678" for s in sets_list):
            sets_list.append({
                "id": 927731678,
                "title": "READING PART 5 6 TEST 1",
                "numTerms": 60
            })
        self.send_json({"sets": sets_list})

    def handle_get_set(self, set_id):
        save_path = DATA_DIR / f"{set_id}.json"
        if save_path.exists():
            with open(save_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self.send_json(d)
        else:
            self.send_json({"status": "error", "message": "Không tìm thấy bộ thẻ"}, 404)

    def send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

app = handler
