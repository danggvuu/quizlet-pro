# Quizlet Pro

Ứng dụng học thẻ bằng tiếng Việt: Learn/SRS, Thẻ nhớ, Tự luận, Trắc nghiệm,
Kiểm tra và Ghép thẻ. Nội dung, tiến độ và bản nháp được lưu trên thiết bị.

## Khởi động

Python 3.10+; Chrome cần thiết nếu tải thẻ từ phiên Quizlet trên máy.

```bash
uv run --with yt-dlp --with curl-cffi python3 server.py
```

Mở **http://127.0.0.1:8888**. Trên macOS có thể mở
`Chay_Quizlet_Pro.command`; macOS/Linux có thể chạy `bash start.sh`.
Script chờ `/api/health` sẵn sàng rồi mới mở trình duyệt.

Server mặc định chỉ nghe `127.0.0.1`, kiểm tra nguồn của yêu cầu ghi và chỉ phục
vụ tài nguyên ứng dụng. Nếu chủ động dùng LAN, cấu hình `QUIZLET_HOST` và
`QUIZLET_ALLOWED_HOSTS` (danh sách hostname/IP, phân cách bằng dấu phẩy).
`PORT` đổi cổng, mặc định 8888. Cần HTTPS để có đầy đủ clipboard/service worker
khi truy cập qua địa chỉ không phải localhost.

> **Lưu ý bảo mật:** API local không có đăng nhập. Chỉ bật lắng nghe LAN trong
> mạng bạn tin cậy; `QUIZLET_ALLOWED_HOSTS` kiểm tra tên host, không cấp quyền
> truy cập. Thiết bị truy cập được server có thể đọc thư viện và gửi bộ thẻ.

## Sử dụng

- **Nhập:** dán văn bản, JSON, chọn file `.json`, hoặc tải từ link Quizlet trên
  server local. Dùng TAB giữa thuật ngữ và định nghĩa để giữ nguyên dấu câu và
  công thức. Dòng không hợp lệ được báo số dòng trước khi lưu.
- **Bookmarklet:** kéo nút trong hướng dẫn lên thanh dấu trang, rồi bấm trên
  trang Quizlet. Xuất các thẻ tìm thấy; đối chiếu số lượng với nguồn. Không
  bảo đảm truy cập được nội dung Quizlet chưa hiển thị hoặc bị giới hạn.
- **Sửa thẻ:** giữ ID, ảnh, mô tả và tiến độ. Bản nháp tự lưu; có thể tiếp tục từ
  thư viện hoặc sau khi tải lại trang.
- **Learn/SRS:** ưu tiên thẻ đến hạn rồi thẻ mới. Đúng lần đầu: ôn sau 5 phút;
  ghi nhớ tiếp: 1 ngày, sau đó tăng gấp đôi đến tối đa 30 ngày. Sai: ôn lại
  ngay. Có nút **Ôn sớm** nếu muốn tiếp tục trước hạn.
- **Lưu phiên:** Learn/Write/Choice lưu hàng đợi, vị trí và phản hồi; Test lưu
  câu hỏi và đáp án; Thẻ nhớ lưu vị trí, thứ tự trộn và mặt đang xem. Nội dung
  hoặc tùy chọn học thay đổi thì bắt đầu lại phiên cho phù hợp.
- **Reset tiến độ:** giữ nguyên các thẻ gắn sao.
- **Xóa học phần:** xóa/ẩn trên thiết bị hiện tại; không xóa bản trên cloud hoặc
  máy khác. Nhập lại JSON cùng ID sẽ khôi phục hiển thị.
- **Xuất:** tải file JSON nội dung bộ thẻ; clipboard chỉ báo thành công sau khi
  sao chép thực sự thành công. File nội dung không chứa tiến độ cá nhân.
- **Chia sẻ:** mở học phần đã tạo → **Chia sẻ** → **Sao chép liên kết**. Người
  nhận mở và học ngay, không cần cùng tài khoản. Liên kết chứa bản nội dung tại
  thời điểm tạo, không chứa tài khoản hay tiến độ học; sửa thẻ rồi chia sẻ lại
  để gửi bản mới. Nội dung được nén trong liên kết, tối đa 64.000 ký tự.
- **Offline:** sau lần tải online và cài service worker thành công, có thể tải
  lại ứng dụng và các bộ mẫu khi mất mạng. Ảnh ngoài trang và giọng đọc online
  vẫn phụ thuộc mạng; phát âm có fallback giọng của trình duyệt.
- **Bàn phím:** `⌘/Ctrl+K` tìm kiếm, `1–4` chọn đáp án, `S` phát âm; Thẻ nhớ:
  `Space` lật, `←/→` chuyển, `F` gắn sao, `R` trộn, `A` tự động.

## Cloud: cá nhân và thư viện chung

Client dùng Firebase SDK 10.13.1, tải độc lập với giao diện cục bộ.

- Chưa đăng nhập: chỉ đọc thư viện chung `quizlet_sets`.
- Đăng nhập Google: đồng bộ bộ thẻ cá nhân dưới
  `users/{uid}/quizlet_sets/{setId}`. Tiến độ và bản nháp vẫn riêng trên thiết bị.
- Các lần đọc thất bại không kích hoạt upload. Ghi sử dụng Firestore transaction
  với revision kỳ vọng; không ghi đè một phiên bản đã thay đổi.
- Khi xung đột, bản local giữ nguyên. Mở bộ đó → Cloud → **Lưu bộ đang mở thành
  bản sao** để giữ và đồng bộ phiên bản riêng. Có thể xuất JSON để sao lưu.
- Nội dung cloud mới được cập nhật vào thư viện local; phiên đang học không bị
  gián đoạn. Mở lại học phần để sử dụng nội dung mới.

### Thiết lập Firebase trên dự án của bạn

1. Cập nhật cấu hình dự án trong `js/cloud.js` nếu dùng dự án khác.
2. Bật **Authentication → Sign-in method → Google**, thêm domain chạy ứng dụng
   vào Authorized domains (kể cả localhost nếu cần).
3. Triển khai nội dung `firestore.rules`: thư viện chung chỉ đọc với client;
   mỗi tài khoản chỉ được truy cập vùng cá nhân của chính mình.

Mã/rules đã được chuẩn bị trong repo; thay đổi phía Firebase Console cần chủ
dự án triển khai. Các kiểm thử dùng cloud giả lập, không thay đổi dự án Firebase
thật và không xác nhận rules đang chạy trên dịch vụ.

`scripts/push_sets_to_firebase.py` dành cho quản trị viên xuất bản thư viện chung,
nhận OAuth access token qua `FIREBASE_ACCESS_TOKEN`. Tài khoản cấp token phải có
quyền IAM ghi Firestore; không mở quyền ghi công khai trong Rules.

## Dữ liệu mẫu

20 bộ mẫu hiện có **1.512 thẻ**, sau khi loại **1.200 dòng trùng hoàn toàn**
trong 9 bộ Part 7. Các bộ này có `sourceWarning` hiển thị trong ứng dụng:
chưa xác minh số thẻ đầy đủ với Quizlet. Loại bản sao không thể khôi phục phần
nội dung chưa tải về.

`scripts/repair_sample_data.py` chỉ bỏ ID có nội dung giống hệt, dừng nếu cùng
ID nhưng nội dung khác. Muốn sửa file, phải truyền `--apply --backup-dir PATH`.
`scrape_all_sets.py` tải lại dữ liệu bằng phiên Chrome, kiểm tra phân trang và
giữ bản cũ khi tải không đủ.

IndexedDB được nâng từ version 1 lên 2 để dùng khóa tiến độ không trùng nhau,
giữ các bản ghi cũ còn tồn tại. Các bản ghi lỗi được cô lập, có nút sửa/xuất/xóa
trong thư viện. Nếu tab cũ chặn nâng cấp, đóng tab đó và tải lại.

## Kiểm thử

```bash
python3 -m unittest discover -s tests -v
node --test tests/study-utils.test.js
```

Giao diện và kiểm thử hồi quy:

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
python3 tests/browser_smoke.py
python3 tests/browser_regressions.py
```

Nếu đã cài Google Chrome, thêm `PLAYWRIGHT_CHANNEL=chrome` trước hai lệnh cuối.
Các bài kiểm tra dùng cổng tạm, hồ sơ trình duyệt riêng và cloud giả lập.
Bộ hồi quy kiểm tra migration, offline, focus, mobile, cloud conflict,
import, giữ phiên, bản nháp và lịch ôn.

## Cấu trúc chính

```text
index.html                  Giao diện và các chế độ học
js/study-utils.js           Chuẩn hóa dữ liệu, nhập văn bản, chấm bài, lịch SRS
js/database.js              IndexedDB và migration
js/session.js               Lưu/khôi phục phiên học
js/cloud.js                 SDK, đăng nhập, đồng bộ có kiểm tra revision
js/navigation.js            Menu, tìm kiếm, focus modal và đăng ký offline
js/editor.js                Bản nháp, sửa dữ liệu cũ, nhập/xuất file
js/bookmarklet.js           Một nguồn bookmarklet dùng chung
sw.js                      Cache ứng dụng và bộ mẫu
server.py                  API local và tải Quizlet
firestore.rules            Quyền truy cập Firebase đề xuất
REVIEW.md                  Báo cáo review và trạng thái khắc phục
```

Phục vụ mục đích học tập cá nhân.
