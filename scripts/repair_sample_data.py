"""Remove only identical repeated IDs, with backups and an explicit source warning."""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import atomic_write_json


def deduplicate(data):
    seen, cards = {}, []
    for card in data["cards"]:
        identity = str(card["id"])
        if identity in seen:
            if seen[identity] != card:
                raise ValueError(f"ID {identity} có nội dung khác nhau; cần đối chiếu thủ công.")
            continue
        seen[identity] = card
        cards.append(card)
    removed = len(data["cards"]) - len(cards)
    if not removed:
        return data, 0
    return {**data, "cards": cards, "numTerms": len(cards),
            "sourceWarning": f"Đã bỏ {removed} dòng lặp từ bản nguồn. Chưa xác minh đủ thẻ với Quizlet."}, removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    if args.apply and not args.backup_dir:
        parser.error("--apply cần --backup-dir")
    changes = []
    for path in sorted((ROOT / "data/sets").glob("*.json")):
        data, removed = deduplicate(json.loads(path.read_text(encoding="utf-8")))
        if removed:
            changes.append((path, data))
            print(f"{path.name}: bỏ {removed} bản sao giống hệt; còn {len(data['cards'])} thẻ.")
    if not args.apply:
        return
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "data/sets.json"
    for path in [manifest_path, *(item[0] for item in changes)]:
        backup = args.backup_dir / path.name
        if backup.exists():
            raise ValueError(f"Không ghi đè bản sao lưu: {backup}")
        shutil.copy2(path, backup)
    for path, data in changes:
        atomic_write_json(path, data)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest:
        path = ROOT / "data/sets" / f"{entry['id']}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        entry["numTerms"] = len(data["cards"])
        if data.get("sourceWarning"):
            entry["sourceWarning"] = data["sourceWarning"]
    atomic_write_json(manifest_path, manifest)


if __name__ == "__main__":
    main()
