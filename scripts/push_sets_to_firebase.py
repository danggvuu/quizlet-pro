#!/usr/bin/env python3
"""
Script đẩy toàn bộ các bộ đề tiếng Anh (20 đề TOEIC) trong data/sets/ lên Firebase Firestore
Dự án: bhjbhj-c8bdd
Collection: quizlet_sets
"""

import os
import sys
import json
import glob
import urllib.request
import urllib.error

PROJECT_ID = "bhjbhj-c8bdd"
COLLECTION = "quizlet_sets"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETS_DIR = os.path.join(BASE_DIR, "data", "sets")

def json_value_to_firestore(val):
    if val is None:
        return {"nullValue": None}
    elif isinstance(val, bool):
        return {"booleanValue": val}
    elif isinstance(val, int):
        return {"integerValue": str(val)}
    elif isinstance(val, float):
        return {"doubleValue": val}
    elif isinstance(val, str):
        return {"stringValue": val}
    elif isinstance(val, list):
        return {"arrayValue": {"values": [json_value_to_firestore(x) for x in val]}}
    elif isinstance(val, dict):
        return {"mapValue": {"fields": {k: json_value_to_firestore(v) for k, v in val.items()}}}
    return {"stringValue": str(val)}

def upload_set_to_firestore(set_data):
    doc_id = str(set_data.get("id"))
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/{COLLECTION}?documentId={doc_id}"
    
    # Firestore REST expects fields map
    fields = {k: json_value_to_firestore(v) for k, v in set_data.items()}
    payload = json.dumps({"fields": fields}).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except urllib.error.HTTPError as e:
        if e.code == 409: # Document already exists, use PATCH
            patch_url = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/{COLLECTION}/{doc_id}"
            patch_req = urllib.request.Request(
                patch_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="PATCH"
            )
            with urllib.request.urlopen(patch_req, timeout=10) as patch_resp:
                return patch_resp.status in (200, 201)
        raise e

def main():
    json_files = glob.glob(os.path.join(SETS_DIR, "*.json"))
    if not json_files:
        print(f"❌ Không tìm thấy file JSON nào trong {SETS_DIR}")
        sys.exit(1)

    print(f"📦 Tìm thấy {len(json_files)} bộ đề tiếng Anh cần đẩy lên Firebase Firestore ({PROJECT_ID})...\n")

    success_count = 0
    permission_error = False

    for i, file_path in enumerate(json_files, 1):
        filename = os.path.basename(file_path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            title = data.get("title", filename)
            num_terms = len(data.get("cards", []))
            print(f"[{i}/{len(json_files)}] Đang đẩy: {title} ({num_terms} thẻ)...", end=" ")
            
            upload_set_to_firestore(data)
            print("✅ Thành công")
            success_count += 1
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("❌ Lỗi 403: Firebase Rules bị khóa!")
                permission_error = True
                break
            else:
                print(f"❌ Lỗi HTTP {e.code}: {e.read().decode('utf-8')[:150]}")
        except Exception as e:
            print(f"❌ Lỗi: {e}")

    if permission_error:
        print("\n⚠️ CHÚ Ý: Firebase Firestore đang chặn quyền ghi (PERMISSION_DENIED)!")
        print("Để đẩy thành công, ông chỉ cần làm 2 bước đơn giản:")
        print("1. Vào: https://console.firebase.google.com/project/bhjbhj-c8bdd/firestore/rules")
        print("2. Đổi rules thành:")
        print("   service cloud.firestore {")
        print("     match /databases/{database}/documents {")
        print("       match /{document=**} {")
        print("         allow read, write: if true;")
        print("       }")
        print("     }")
        print("   }")
        print("3. Bấm 'Publish' rồi chạy lại lệnh: python3 scripts/push_sets_to_firebase.py\n")
    else:
        print(f"\n🎉 Hoàn thành! Đã đẩy thành công {success_count}/{len(json_files)} bộ đề lên Firestore!")

if __name__ == "__main__":
    main()
