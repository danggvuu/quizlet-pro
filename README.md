# 🚀 Quizlet Pro - Ôn Thi Miễn Phí (Learn & Write Mode)

Một ứng dụng web mã nguồn mở mô phỏng và nâng cấp toàn bộ các tính năng học tập cốt lõi của Quizlet (hoàn toàn miễn phí, không giới hạn lượt học, không bắt đăng ký tài khoản Plus).

---

## ✨ Tính năng nổi bật

- 📥 **Tự động cào dữ liệu từ link Quizlet:**
  - Nhập đường link bất kỳ (VD: `https://quizlet.com/vn/927731678/...`).
  - Tự động vượt rào bảo mật Cloudflare Turnstile.
  - Cào trọn vẹn **Thuật ngữ**, **Định nghĩa** và **Toàn bộ hình ảnh minh họa**.
  - Lưu vĩnh viễn dữ liệu về máy để học offline.

- 🎯 **Chế độ Học (Learn Mode - SRS):**
  - Thuật toán lặp lại ngắt quãng (Spaced Repetition System) 3 cấp độ: *Chưa học* $\rightarrow$ *Đang học* $\rightarrow$ *Thành thạo*.
  - Chia bài học theo các vòng (Rounds), tổng kết tiến độ sau mỗi vòng.
  - Hiệu ứng pháo hoa ăn mừng khi hoàn thành 100%.

- ✍️ **Chế độ Tự luận (Written / Gõ phím):**
  - Giao diện gõ phím chuẩn Quizlet Write.
  - So khớp từ thông minh (bỏ qua viết hoa/thường, dấu cách và dấu câu phụ).
  - Bắt buộc gõ lại đáp án đúng khi trả lời sai để ghi nhớ sâu.
  - Nút duyệt *"Tôi đã trả lời đúng"* khi cần.

- 🔤 **Chế độ Trắc nghiệm (Multiple Choice):**
  - 4 lựa chọn ngẫu nhiên, hỗ trợ phím tắt số `1`, `2`, `3`, `4`.

- 🃏 **Chế độ Thẻ ghi nhớ (Flashcards):**
  - Lật mặt trước/sau bằng phím `Space`, chuyển thẻ bằng phím mũi tên `←` `→`.

- 🔊 **Phát âm HD Studio (Google TTS):**
  - Giọng đọc bản xứ chuẩn Mỹ, trong trẻo, không bị ngắt tiếng hay lỗi trình duyệt.
  - Phím tắt **`S`** để nghe phát âm từ vựng bất kỳ lúc nào.

- ⚙️ **Tùy biến học tập chuyên sâu:**
  - Đảo chiều câu hỏi: Tiếng Anh $\rightarrow$ Tiếng Việt hoặc Tiếng Việt $\rightarrow$ Tiếng Anh.
  - Chế độ *"Chỉ học các từ được gắn sao (★)"*.
  - Chế độ Giao diện ban đêm (Dark Mode) bảo vệ mắt.

---

## 🛠️ Yêu cầu & Cài đặt

### Yêu cầu hệ thống:
- Python 3.10+
- macOS / Linux / Windows
- Trình duyệt Google Chrome (để giải mã cookie Cloudflare khi cào thẻ)

### Khởi động nhanh bằng `uv`:
```bash
uv run --with yt-dlp --with curl-cffi python3 server.py
```

Sau đó mở trình duyệt và truy cập: **`http://localhost:8888`**

---

## 📂 Cấu trúc dự án

```text
quizlet_pro/
├── server.py              # Backend HTTP server & Quizlet Scraper
├── index.html             # Frontend SPA tương tác (Tailwind-like Quizlet UI)
├── requirements.txt       # Các thư viện phụ thuộc
├── README.md              # Tài liệu hướng dẫn sử dụng
└── data/
    └── sets/              # Thư mục lưu trữ các bộ thẻ JSON
```

---

## 📝 Giấy phép
Dự án được phân phối phi thương mại phục vụ mục đích học tập cá nhân.
