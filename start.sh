#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "🚀 Đang khởi động Quizlet Pro..."
uv run --with yt-dlp --with curl-cffi python3 server.py &
sleep 2
open "http://localhost:8888"
