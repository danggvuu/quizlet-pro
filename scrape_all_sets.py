import os
import json
import time
from pathlib import Path
from yt_dlp.cookies import extract_cookies_from_browser
from curl_cffi import requests

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "sets"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CLASS_SETS_ORDER = [
    # Part 5 & 6 (Test 1 -> 10)
    ("927731678", "READING PART 5 6 TEST 1"),
    ("927731707", "READING PART 5 6 TEST 2"),
    ("927731719", "READING PART 5 6 TEST 3"),
    ("927731732", "READING PART 5 6 TEST 4"),
    ("927731743", "READING PART 5 6 TEST 5"),
    ("927731753", "READING PART 5 6 TEST 6"),
    ("927731770", "READING PART 5 6 TEST 7"),
    ("927731825", "READING PART 5 6 TEST 8"),
    ("927731839", "READING PART 5 6 TEST 9"),
    ("927731856", "READING PART 5 TEST 10"),
    # Part 7 (Test 1 -> 10)
    ("1024619363", "READING - PART 7 - TEST 1"),
    ("1007017985", "READING PART 7 - TEST 02"),
    ("1008990116", "READING PART 7 - TEST 3"),
    ("1010710706", "READING PART 7 - TEST 4"),
    ("1012039369", "READING PART 7 - TEST 5"),
    ("1013575766", "READING PART 7 - TEST 06"),
    ("1015913274", "READING PART 7 - TEST 07"),
    ("1020661698", "READING PART 7 - TEST 08"),
    ("1022004296", "READING PART 7 - TEST 9"),
    ("1023641138", "READING PART 7 - TEST 10"),
]

def main():
    print("=== BẮT ĐẦU CÀO TOÀN BỘ 20 BỘ ĐỀ TRONG LỚP ETS 2020 CÔ DIỄM (FULL 100% THẺ) ===")
    
    # 1. Extract cookies from Chrome
    jar = extract_cookies_from_browser("chrome")
    cookies = {c.name: c.value for c in jar if "quizlet" in c.domain}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://quizlet.com/"
    }

    manifest_entries = []

    for idx, (set_id, fallback_title) in enumerate(CLASS_SETS_ORDER, 1):
        save_path = DATA_DIR / f"{set_id}.json"

        # Fetch clean metadata
        title = fallback_title
        description = ""
        expected_terms = 0
        try:
            r_meta = requests.get(f"https://quizlet.com/webapi/3.4/sets/{set_id}", cookies=cookies, headers=headers, impersonate="chrome120", timeout=8)
            if r_meta.status_code == 200:
                s_obj = r_meta.json()["responses"][0]["models"]["set"][0]
                title = s_obj.get("title", fallback_title).strip()
                description = s_obj.get("description", "").strip()
                expected_terms = s_obj.get("numTerms", 0)
        except Exception as e:
            print("  Lỗi lấy title:", e)

        # Check if already fully cached
        if save_path.exists():
            try:
                with open(save_path, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if len(cached.get("cards", [])) >= expected_terms and expected_terms > 0:
                        print(f"[{idx}/20] ✓ Đã đủ 100%: {title} ({len(cached['cards'])}/{expected_terms} thẻ)")
                        manifest_entries.append({
                            "id": str(set_id),
                            "title": title,
                            "numTerms": len(cached["cards"])
                        })
                        continue
            except Exception:
                pass

        print(f"[{idx}/20] ⏳ Đang cào full {expected_terms} thẻ của: {title}...")

        # Fetch items across pages using pagingToken
        all_items = []
        paging_token = None
        while True:
            api_url = f"https://quizlet.com/webapi/3.4/studiable-item-documents?filters%5BstudiableContainerId%5D={set_id}&filters%5BstudiableContainerType%5D=1&perPage=100"
            if paging_token:
                api_url += f"&pagingToken={paging_token}"

            try:
                r_api = requests.get(api_url, cookies=cookies, headers=headers, impersonate="chrome120", timeout=12)
                if r_api.status_code != 200:
                    break
                data = r_api.json()
                resp = data.get("responses", [{}])[0]
                items = resp.get("models", {}).get("studiableItem", [])
                if not items:
                    break
                all_items.extend(items)
                paging = resp.get("paging", {})
                total = paging.get("total", len(all_items))
                paging_token = paging.get("token")
                if len(all_items) >= total or not paging_token:
                    break
            except Exception as e:
                print(f"  Lỗi token {paging_token}:", e)
                break

        # Parse terms, definitions, images
        cards = []
        images_count = 0
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
                        if image:
                            images_count += 1
            cards.append({
                "id": it.get("id"),
                "term": term,
                "definition": definition,
                "image": image
            })

        set_obj = {
            "id": str(set_id),
            "title": title,
            "description": description,
            "numTerms": len(cards),
            "cards": cards
        }

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(set_obj, f, ensure_ascii=False, indent=2)

        print(f"  🎉 Hoàn thành: {title} | {len(cards)} thuật ngữ | {images_count} ảnh")
        manifest_entries.append({
            "id": str(set_id),
            "title": title,
            "numTerms": len(cards)
        })
        time.sleep(0.3)

    # Save to data/sets.json
    manifest_path = BASE_DIR / "data" / "sets.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_entries, f, ensure_ascii=False, indent=2)

    total_all_cards = sum(e["numTerms"] for e in manifest_entries)
    print(f"\n✓ ĐÃ CÀO XONG TOÀN BỘ {len(manifest_entries)} BỘ ĐỀ! TỔNG CỘNG: {total_all_cards} TỪ VỰNG & ẢNH!")

if __name__ == "__main__":
    main()
