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
import threading
import uuid
import tempfile
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

PORT = int(os.environ.get("PORT", "8888"))
HOST = os.environ.get("QUIZLET_HOST", "127.0.0.1")
MAX_BODY_BYTES = 5 * 1024 * 1024
SET_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
MANIFEST_LOCK = threading.Lock()


def atomic_write_json(path, value):
    """Publish a complete JSON file, never a partially written one."""
    path = Path(path)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def fetch_studiable_items(requests, set_id, cookies, headers):
    """Follow Quizlet's cursor and reject incomplete/repeated pages."""
    items = []
    seen_ids = set()
    seen_tokens = set()
    token = None
    while True:
        params = {
            "filters[studiableContainerId]": set_id,
            "filters[studiableContainerType]": 1,
            "perPage": 100,
        }
        if token:
            params["pagingToken"] = token
        url = "https://quizlet.com/webapi/3.4/studiable-item-documents?" + urllib.parse.urlencode(params)
        response = requests.get(url, cookies=cookies, headers=headers, impersonate="chrome120", timeout=12)
        if response.status_code != 200:
            raise ValueError(f"Không tải đủ bộ thẻ (HTTP {response.status_code}). Hãy xác minh trên Quizlet hoặc nhập thủ công.")
        responses = response.json().get("responses") or []
        if not responses:
            raise ValueError("Quizlet trả về dữ liệu không hợp lệ.")
        result = responses[0]
        page = result.get("models", {}).get("studiableItem", [])
        for item in page:
            identity = str(item.get("id"))
            if item.get("id") is None or identity in seen_ids:
                raise ValueError("Quizlet trả về trang thẻ lặp hoặc thiếu ID; bản cũ được giữ nguyên.")
            seen_ids.add(identity)
            items.append(item)
        paging = result.get("paging", {})
        total = paging.get("total")
        if total is not None and len(items) >= int(total):
            return items
        next_token = paging.get("token")
        if not next_token:
            if total is not None and len(items) < int(total):
                raise ValueError("Quizlet thiếu trang dữ liệu; bản cũ được giữ nguyên.")
            return items
        if not page or next_token in seen_tokens:
            raise ValueError("Phân trang Quizlet không tiến triển; bản cũ được giữ nguyên.")
        seen_tokens.add(next_token)
        token = next_token

def extract_set_id(url_or_text):
    m = re.search(r"(\d{6,})", str(url_or_text))
    return m.group(1) if m else None


def extract_quizlet_cookies(cookie_jar):
    """Only forward cookies that the Quizlet apex host would receive."""
    return {
        cookie.name: cookie.value
        for cookie in cookie_jar
        if cookie.domain.lstrip(".").lower() == "quizlet.com"
    }

def update_manifest(set_id, title, count):
    if IS_VERCEL:
        return
    try:
        manifest_path = BASE_DIR / "data" / "sets.json"
        with MANIFEST_LOCK:
            sets_list = []
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    sets_list = json.load(f)
            sets_list = [s for s in sets_list if str(s.get("id")) != str(set_id)]
            sets_list.append({"id": str(set_id), "title": title, "numTerms": count})
            atomic_write_json(manifest_path, sets_list)
    except Exception as e:
        print("update_manifest error:", e)

def scrape_quizlet(set_id, raw_url=None):
    if not re.fullmatch(r"\d{6,}", str(set_id)):
        raise ValueError("ID Quizlet không hợp lệ.")
    url = f"https://quizlet.com/{set_id}/"

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
        cookies = extract_quizlet_cookies(jar)
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
    all_items = fetch_studiable_items(requests, set_id, cookies, headers)

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
    atomic_write_json(save_path, set_obj)

    update_manifest(set_id, title, len(cards))

    return set_obj

class handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, directory=str(BASE_DIR), **kwargs)
        except TypeError:
            super().__init__(*args, **kwargs)

    def do_OPTIONS(self):
        if not self.valid_write_origin():
            self.send_json({"status": "error", "message": "Nguồn yêu cầu không được phép."}, 403)
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def valid_write_origin(self):
        host = self.headers.get("Host", "")
        try:
            hostname = urllib.parse.urlparse("//" + host).hostname
        except ValueError:
            return False
        allowed = {"localhost", "127.0.0.1", "::1"}
        allowed.update(filter(None, os.environ.get("QUIZLET_ALLOWED_HOSTS", "").split(",")))
        if HOST not in ("0.0.0.0", "::"):
            allowed.add(HOST)
        if hostname not in allowed or self.headers.get("Sec-Fetch-Site") == "cross-site":
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin == f"http://{host}"

    def send_head(self):
        # SimpleHTTPRequestHandler otherwise exposes source, .git and .venv.
        path = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        target = Path(self.translate_path(self.path)).resolve()
        allowed = (
            path in ("/", "/index.html", "/sw.js", "/data/sets.json")
            or re.fullmatch(r"/js/[A-Za-z0-9_-]+\.js", path)
            or re.fullmatch(r"/data/sets/[A-Za-z0-9_-]+\.json", path)
        )
        if not allowed or not target.is_relative_to(BASE_DIR):
            self.send_error(404)
            return None
        return super().send_head()

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
        elif parsed.path == "/api/health":
            self.send_json({"app": "quizlet-pro", "status": "ok"})
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
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length < 0 or content_length > MAX_BODY_BYTES:
                self.send_json({"status": "error", "message": "Dữ liệu gửi lên quá lớn."}, 413)
                return
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        except (ValueError, UnicodeError):
            self.send_json({"status": "error", "message": "Dữ liệu JSON không hợp lệ."}, 400)
            return
        if not self.valid_write_origin():
            self.send_json({"status": "error", "message": "Nguồn yêu cầu không được phép."}, 403)
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json({"status": "error", "message": "Yêu cầu Content-Type: application/json."}, 415)
            return
        try:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON phải là object.")
        except (ValueError, UnicodeError):
            self.send_json({"status": "error", "message": "Dữ liệu JSON không hợp lệ."}, 400)
            return

        if parsed.path == "/api/scrape":
            try:
                url = payload.get("url", "")
                if not isinstance(url, str):
                    self.send_json({"status": "error", "message": "URL phải là văn bản."}, 400)
                    return
                url = url.strip()
                parsed_url = urllib.parse.urlparse(url)
                if parsed_url.scheme not in ("http", "https") or parsed_url.hostname not in ("quizlet.com", "www.quizlet.com"):
                    self.send_json({"status": "error", "message": "Chỉ hỗ trợ đường link quizlet.com hợp lệ."}, 400)
                    return
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
            try:
                title = payload.get("title", "Bộ thẻ tự tạo")
                cards = payload.get("cards", [])
                if not isinstance(title, str) or not isinstance(cards, list) or not cards:
                    self.send_json({"status": "error", "message": "Danh sách thẻ trống!"}, 400)
                    return
                title = title.strip() or "Bộ thẻ tự tạo"
                requested_id = str(payload.get("id") or "")
                if requested_id and not SET_ID_RE.fullmatch(requested_id):
                    self.send_json({"status": "error", "message": "ID bộ thẻ không hợp lệ."}, 400)
                    return
                set_id = requested_id if SET_ID_RE.fullmatch(requested_id) else f"custom_{uuid.uuid4().hex}"
                normalized_cards = []
                seen_ids = set()
                for index, card in enumerate(cards):
                    if not isinstance(card, dict) or not isinstance(card.get("term"), str) or not isinstance(card.get("definition"), str):
                        self.send_json({"status": "error", "message": f"Thẻ {index + 1} không hợp lệ."}, 400)
                        return
                    term = card["term"].strip()
                    definition = card["definition"].strip()
                    if not term and not definition:
                        self.send_json({"status": "error", "message": f"Thẻ {index + 1} đang trống."}, 400)
                        return
                    if not term or not definition:
                        self.send_json({"status": "error", "message": f"Thẻ {index + 1} cần đủ hai mặt."}, 400)
                        return
                    card_id = card.get("id")
                    if not isinstance(card_id, (str, int)) or isinstance(card_id, bool):
                        card_id = uuid.uuid4().hex
                    if str(card_id) in seen_ids:
                        self.send_json({"status": "error", "message": "ID thẻ trùng nhau."}, 400)
                        return
                    seen_ids.add(str(card_id))
                    normalized_cards.append({
                        "id": card_id,
                        "term": term,
                        "definition": definition,
                        "image": card.get("image", "") if isinstance(card.get("image", ""), str) else ""
                    })
                cards = normalized_cards
                if not cards:
                    self.send_json({"status": "error", "message": "Không có thẻ hợp lệ."}, 400)
                    return
                set_obj = {
                    "id": set_id,
                    "title": title,
                    "description": payload.get("description", "Nhập thủ công"),
                    "numTerms": len(cards),
                    "cards": cards
                }
                save_path = DATA_DIR / f"{set_id}.json"
                atomic_write_json(save_path, set_obj)
                update_manifest(set_id, title, len(cards))
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
        if not SET_ID_RE.fullmatch(set_id):
            self.send_json({"status": "error", "message": "ID bộ thẻ không hợp lệ."}, 400)
            return
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
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

# Vercel entrypoint exports
QuizletAppHandler = handler
app = handler

if __name__ == "__main__":
    class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        daemon_threads = True
        allow_reuse_address = True

    with ThreadingServer((HOST, PORT), handler) as httpd:
        print(f"Server Quizlet Pro đang chạy tại: http://localhost:{PORT}")
        httpd.serve_forever()
