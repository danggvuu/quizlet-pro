#!/bin/bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
PORT="${PORT:-8888}"
URL="http://127.0.0.1:$PORT"

ready() {
  curl --fail --silent --max-time 1 "$URL/api/health" 2>/dev/null | grep -q '"app": "quizlet-pro"'
}

if ! ready; then
  echo "Đang khởi động Quizlet Pro..."
  if [ -x "$DIR/.venv/bin/python3" ]; then
    "$DIR/.venv/bin/python3" server.py &
  elif command -v uv >/dev/null 2>&1; then
    uv run --with curl-cffi --with yt-dlp python3 server.py &
  else
    python3 server.py &
  fi
  SERVER_PID=$!
  for ((i=0; i<120; i++)); do
    if ready; then break; fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      echo "Server đã dừng. Kiểm tra lỗi bên trên (ví dụ cổng $PORT đang được dùng)." >&2
      exit 1
    fi
    sleep 0.5
  done
  if ! ready; then
    echo "Server chưa sẵn sàng. Xem lỗi bên trên hoặc mở $URL khi khởi động xong." >&2
    exit 1
  fi
fi

echo "Quizlet Pro: $URL"
if command -v open >/dev/null 2>&1; then
  open "$URL"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL"
else
  echo "Mở địa chỉ trên trong trình duyệt."
fi
