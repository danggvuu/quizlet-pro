#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "🚀 Đang khởi động Quizlet Pro siêu tốc..."

# Sử dụng virtualenv đã tạo sẵn để chạy tức thì trong 0.05 giây (không tải lại thư viện)
if [ -f "$DIR/.venv/bin/python3" ]; then
  "$DIR/.venv/bin/python3" server.py &
elif command -v uv &>/dev/null; then
  uv run --with curl-cffi python3 server.py &
else
  python3 server.py &
fi

# Chờ server mở cổng 8888 xong là bật trình duyệt ngay lập tức (không chờ thừa)
for i in {1..40}; do
  if curl -s -I "http://localhost:8888" &>/dev/null; then
    break
  fi
  sleep 0.05
done

open "http://localhost:8888"
