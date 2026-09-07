import http.server
import socketserver
import json
import os
import re
import shutil
import urllib.parse
import urllib.request
import subprocess
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Trên Vercel môi trường lambda là read-only, sử dụng /tmp nếu đang chạy trên Vercel
IS_VERCEL = bool(os.environ.get("VERCEL"))
if IS_VERCEL:
    DATA_DIR = Path("/tmp/sets")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Sao chép các bộ thẻ gốc từ repository sang /tmp
    src_data = BASE_DIR / "data" / "sets"
    if src_data.exists():
        for f in src_data.glob("*.json"):
            dst = DATA_DIR / f.name
            if not dst.exists():
                try:
                    shutil.copy(f, dst)
                except Exception:
                    pass
else:
    DATA_DIR = BASE_DIR / "data" / "sets"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

PORT = 8888

def extract_set_id(url_or_text):
    m = re.search(r"(\d{6,})", str(url_or_text))
    return m.group(1) if m else None

def scrape_quizlet(set_id, raw_url=None):
    url = raw_url if (raw_url and "quizlet.com" in raw_url) else f"https://quizlet.com/{set_id}/"

    # 1. Thử mở Chrome trên máy local Mac nếu có
    if not IS_VERCEL:
        try:
            subprocess.run(["osascript", "-e", f'tell application "Google Chrome" to open location "{url}"'], check=False)
            time.sleep(2.5)
        except Exception as e:
            print("Note opening Chrome:", e)

    # 2. Đọc cookie (chỉ hoạt động trên local máy có Chrome)
    cookies = {}
    try:
        from yt_dlp.cookies import extract_cookies_from_browser
        jar = extract_cookies_from_browser("chrome")
        cookies = {c.name: c.value for c in jar if "quizlet" in c.domain}
    except Exception as e:
        print("Note extracting cookies:", e)

    try:
        from curl_cffi import requests
    except ImportError:
        raise Exception("Thiếu thư viện curl-cffi. Vui lòng chạy uv run --with curl-cffi.")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://quizlet.com/",
    }

    # 3. Lấy metadata
    title = f"Bộ thẻ {set_id}"
    description = ""
    try:
        r_page = requests.get(url, cookies=cookies, headers={
            "User-Agent": headers["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://quizlet.com/"
        }, impersonate="chrome120", timeout=8)
        if "__NEXT_DATA__" in r_page.text:
            m = re.search(r"<script id=\"__NEXT_DATA__\" type=\"application/json\">(.*?)</script>", r_page.text)
            if m:
                nd = json.loads(m.group(1))
                dehydrated = nd.get("props", {}).get("pageProps", {}).get("dehydratedReduxStateKey", "")
                if dehydrated:
                    s_data = json.loads(dehydrated).get("setPage", {}).get("set", {})
                    title = s_data.get("title", title)
                    description = s_data.get("description", description)
    except Exception as e:
        print("Warning page metadata:", e)

    # 4. Tải items qua API
    all_items = []
    page = 1
    while True:
        api_url = f"https://quizlet.com/webapi/3.4/studiable-item-documents?filters%5BstudiableContainerId%5D={set_id}&filters%5BstudiableContainerType%5D=1&page={page}&perPage=100"
        r_api = requests.get(api_url, cookies=cookies, headers=headers, impersonate="chrome120", timeout=12)
        if r_api.status_code != 200:
            if page == 1:
                if IS_VERCEL:
                    raise Exception(f"Lỗi Cloudflare (Mã: {r_api.status_code}). Trên bản Vercel online, Cloudflare chặn máy chủ đám mây. Vui lòng bấm nút ➕ Nhập thủ công (Copy-Paste) hoặc chạy app trên máy tính bằng file Chay_Quizlet_Pro.command để cào tự động nhé!")
                raise Exception(f"Cloudflare yêu cầu xác minh (Mã: {r_api.status_code}). Hãy nhìn sang tab Chrome vừa mở, tick vào ô xác minh rồi bấm lại nhé!")
            break

        data = r_api.json()
        resp = data.get("responses", [{}])[0]
        items = resp.get("models", {}).get("studiableItem", [])
        if not items:
            break
        all_items.extend(items)

        paging = resp.get("paging", {})
        total = paging.get("total", len(all_items))
        if len(all_items) >= total or len(items) == 0:
            break
        page += 1

    if not all_items:
        raise Exception("Không tìm thấy thẻ nào trong bộ đề này.")

    # 5. Phân tích bóc tách từ, nghĩa, ảnh
    cards = []
    for it in all_items:
        term = ""
        definition = ""
        image = ""
        for s in it.get("cardSides", []):
            label = s.get("label")
            for m in s.get("media", []):
                if m.get("type") == 1:
                    if label == "word":
                        term = m.get("plainText", "")
                    elif label == "definition":
                        definition = m.get("plainText", "")
                elif m.get("type") == 2:
                    image = m.get("url", "")
        cards.append({
            "id": it.get("id"),
            "term": term,
            "definition": definition,
            "image": image
        })

    set_obj = {
        "id": set_id,
        "title": title,
        "description": description,
        "numTerms": len(cards),
        "cards": cards
    }

    save_path = DATA_DIR / f"{set_id}.json"
    try:
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(set_obj, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Save to disk error:", e)

    return set_obj

class handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, directory=str(BASE_DIR), **kwargs)
        except TypeError:
            super().__init__(*args, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            with open(BASE_DIR / "index.html", "rb") as f:
                self.wfile.write(f.read())
            return
        elif parsed.path == "/api/sets":
            self.handle_list_sets()
            return
        elif parsed.path.startswith("/api/sets/"):
            set_id = parsed.path.replace("/api/sets/", "").strip()
            self.handle_get_set(set_id)
            return
        elif parsed.path == "/api/tts":
            self.handle_tts(parsed.query)
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/scrape":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                payload = json.loads(body)
                url = payload.get("url", "").strip()
                set_id = extract_set_id(url)
                if not set_id:
                    self.send_json({"status": "error", "message": "Không tìm thấy ID bộ thẻ trong đường link bạn nhập!"}, 400)
                    return

                set_obj = scrape_quizlet(set_id, raw_url=url)
                self.send_json({"status": "ok", "set": set_obj})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)
            return
        elif parsed.path == "/api/manual-import":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                payload = json.loads(body)
                title = payload.get("title", "Bộ thẻ tự tạo").strip() or "Bộ thẻ tự tạo"
                cards = payload.get("cards", [])
                if not cards:
                    self.send_json({"status": "error", "message": "Danh sách thẻ trống!"}, 400)
                    return
                set_id = payload.get("id") or f"custom_{int(time.time())}"
                set_obj = {
                    "id": set_id,
                    "title": title,
                    "description": payload.get("description", "Nhập thủ công"),
                    "numTerms": len(cards),
                    "cards": cards
                }
                save_path = DATA_DIR / f"{set_id}.json"
                try:
                    with open(save_path, "w", encoding="utf-8") as f:
                        json.dump(set_obj, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                self.send_json({"status": "ok", "set": set_obj})
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)
            return

        self.send_response(404)
        self.end_headers()

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
        req = urllib.request.Request(tts_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
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
            print("TTS Error:", e)
            self.send_response(500)
            self.end_headers()

    def handle_list_sets(self):
        sets_list = []
        # Lấy từ cả BASE_DIR và DATA_DIR
        search_dirs = [DATA_DIR]
        if BASE_DIR / "data" / "sets" != DATA_DIR and (BASE_DIR / "data" / "sets").exists():
            search_dirs.append(BASE_DIR / "data" / "sets")

        seen_ids = set()
        for s_dir in search_dirs:
            for p in s_dir.glob("*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        d = json.load(f)
                        sid = str(d.get("id"))
                        if sid not in seen_ids:
                            seen_ids.add(sid)
                            sets_list.append({
                                "id": d.get("id"),
                                "title": d.get("title", p.stem),
                                "numTerms": d.get("numTerms", len(d.get("cards", [])))
                            })
                except Exception:
                    pass
        self.send_json({"sets": sets_list})

    def handle_get_set(self, set_id):
        save_path = DATA_DIR / f"{set_id}.json"
        if not save_path.exists():
            save_path = BASE_DIR / "data" / "sets" / f"{set_id}.json"
        if not save_path.exists():
            self.send_json({"status": "error", "message": "Không tìm thấy bộ thẻ"}, 404)
            return
        with open(save_path, "r", encoding="utf-8") as f:
            d = json.load(f)
        self.send_json(d)

    def send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

# Vercel entrypoint exports
QuizletAppHandler = handler
app = handler

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"Server Quizlet Pro đang chạy tại: http://localhost:{PORT}")
        httpd.serve_forever()
