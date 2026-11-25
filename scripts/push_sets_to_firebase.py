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
import urllib.parse
import re

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
    token = os.environ.get("FIREBASE_ACCESS_TOKEN")
    if not token:
        raise ValueError("Thiếu FIREBASE_ACCESS_TOKEN.")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    doc_id = set_data.get("id")
    if not isinstance(doc_id, (str, int)) or isinstance(doc_id, bool):
        raise ValueError("ID bộ thẻ Firestore không hợp lệ.")
    doc_id = str(doc_id)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", doc_id):
        raise ValueError("ID bộ thẻ Firestore không hợp lệ.")
    encoded_doc_id = urllib.parse.quote(doc_id, safe="")
    url = (
        f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)"
        f"/documents/{COLLECTION}?{urllib.parse.urlencode({'documentId': doc_id})}"
    )
    
    # Firestore REST expects fields map
    fields = {k: json_value_to_firestore(v) for k, v in set_data.items()}
    payload = json.dumps({"fields": fields}).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 201)
    except urllib.error.HTTPError as e:
        if e.code == 409: # Document already exists, use PATCH
            patch_url = (
                f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)"
                f"/documents/{COLLECTION}/{encoded_doc_id}"
            )
            patch_req = urllib.request.Request(
                patch_url,
                data=payload,
                headers=headers,
                method="PATCH"
            )
            with urllib.request.urlopen(patch_req, timeout=10) as patch_resp:
                return patch_resp.status in (200, 201)
        raise e

def main():
    token = os.environ.get("FIREBASE_ACCESS_TOKEN")
    if not token:
        print("Cần FIREBASE_ACCESS_TOKEN của tài khoản quản trị có quyền Firestore.")
        print("Ví dụ lấy access token bằng gcloud auth print-access-token, rồi đặt vào biến môi trường.")
        sys.exit(1)
    json_files = glob.glob(os.path.join(SETS_DIR, "*.json"))
    if not json_files:
        print(f"❌ Không tìm thấy file JSON nào trong {SETS_DIR}")
        sys.exit(1)

    print(f"📦 Tìm thấy {len(json_files)} bộ đề tiếng Anh cần đẩy lên Firebase Firestore ({PROJECT_ID})...\n")

    success_count = 0
    permission_error = False
    failure_count = 0

    for i, file_path in enumerate(json_files, 1):
        filename = os.path.basename(file_path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            title = data.get("title", filename)
            num_terms = len(data.get("cards", []))
            print(f"[{i}/{len(json_files)}] Đang đẩy: {title} ({num_terms} thẻ)...", end=" ")
            
            if not upload_set_to_firestore(data):
                failure_count += 1
                print("❌ Firestore không xác nhận thao tác thành công.")
                continue
            print("✅ Thành công")
            success_count += 1
        except urllib.error.HTTPError as e:
            failure_count += 1
            if e.code == 403:
                print("❌ Lỗi 403: token hoặc quyền IAM không cho phép ghi Firestore.")
                permission_error = True
                break
            else:
                print(f"❌ Lỗi HTTP {e.code}: {e.read().decode('utf-8')[:150]}")
        except Exception as e:
            failure_count += 1
            print(f"❌ Lỗi: {e}")

    if permission_error:
        print("Tài khoản quản trị chưa có quyền ghi. Kiểm tra IAM và token; giữ thư viện chung ở chế độ chỉ đọc với client.")
        sys.exit(1)
    else:
        print(f"\n🎉 Hoàn thành! Đã đẩy thành công {success_count}/{len(json_files)} bộ đề lên Firestore!")
        if failure_count:
            sys.exit(1)

if __name__ == "__main__":
    main()
