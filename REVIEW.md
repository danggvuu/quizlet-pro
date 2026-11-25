# Kiểm tra lỗi và trải nghiệm người dùng — 16/11/2026

## Cập nhật khắc phục

15 lỗi xác nhận bên dưới đã được xử lý trong mã nguồn. Các phần sau mục này
là **bản ghi review trước khi sửa**, nên số dòng và mô tả hành vi cũ chỉ để đối chiếu.

| Lỗi | Khắc phục |
| --- | --- |
| 1–2 Cloud | Tách lỗi đọc khỏi kết quả rỗng; cập nhật revision; transaction compare-and-swap; giữ bản local khi xung đột |
| 3 Dữ liệu cũ lỗi | Cô lập từng bộ, thư viện vẫn mở; nút sửa/xuất bản gốc/xóa |
| 4 Nhập văn bản | Ưu tiên TAB, tách một lần, báo dòng lỗi trước khi lưu |
| 5 Nhập lại sau xóa | Gỡ ID khỏi danh sách ẩn sau khi lưu thành công |
| 6 Đổi học phần lỗi | Trạng thái loading/error riêng, xóa nội dung cũ và khóa thao tác |
| 7 Mobile | Nhóm nút xuống dòng, select có min-width phù hợp |
| 8 Phiên học | Lưu queue/phản hồi, đáp án Test, thứ tự/mặt Flashcards; kiểm tra content identity |
| 9 Reset | Giữ sao nhất quán ở cả hai nút, lưu lại tiến độ |
| 10 Override | Khôi phục trạng thái trước đáp án rồi chấm lại |
| 11 Thẻ rỗng | Chặn nhập mới thiếu mặt; thẻ cũ thiếu mặt chỉ xem Flashcards và sửa |
| 12 Bookmarklet | Một nguồn ở `js/bookmarklet.js`, dùng origin hiện tại, file JSON cho dữ liệu lớn |
| 13 SDK offline | UI Cloud độc lập; tải SDK động, có xử lý lỗi |
| 14 Khóa progress | JSON tuple; migration IndexedDB v2 bảo toàn bản ghi cũ còn tồn tại |
| 15 Focus modal | Trap Tab/Shift+Tab, inert nền, Escape và phục hồi focus |

Đã bổ sung bản nháp, nhập file JSON, cache offline, lịch SRS theo thời gian,
khởi động chờ health check, server mặc định loopback và kiểm tra Origin.
Cloud cá nhân sử dụng đăng nhập Google và đường dẫn theo UID; thư viện chung
chỉ đọc. `firestore.rules` và hướng dẫn triển khai ở README.

Đã sao lưu rồi bỏ 1.200 bản sao giống hệt, còn 1.512 thẻ mẫu. Bản sao lưu gốc:
`/private/var/folders/22/4g3rpp7938j_9gslhj958cgh0000gn/T/opencode/quizlet-original-sets-20261116`.
Chưa thể khôi phục dữ liệu chưa tải hoặc tiến độ đã bị ghi đè trước migration.
Các bộ nguồn có cảnh báo cần đối chiếu Quizlet.

Kiểm thử hồi quy ở `tests/browser_regressions.py`; kiểm tra cloud dùng giả lập,
không triển khai Rules hay bật Google Authentication trên dự án Firebase thật.

## Phạm vi và kết quả

Đã rà frontend, IndexedDB, API Python, các script tải/đẩy dữ liệu, script khởi
động, cấu hình và 20 bộ dữ liệu mẫu. Đã chạy:

- 4 kiểm thử Node: đạt.
- 5 kiểm thử Python: đạt.
- `tests/browser_smoke.py` bằng Chrome: đạt.
- Các tình huống bổ sung bằng Chrome với hồ sơ trình duyệt riêng: phát hiện
  những lỗi bên dưới. Các kiểm thử hiện tại chưa bao phủ các tình huống này.

Cloud được giả lập tại `window.CloudDB`; không truy cập hay sửa dữ liệu Firebase
thật. Chưa xác minh dịch vụ Quizlet/Firebase/TTS trực tuyến, Safari/iOS thật hoặc
quy tắc Firestore đang triển khai. Các vị trí dòng tham chiếu là mã tại thời điểm
review ban đầu. Xem trạng thái khắc phục ở đầu tài liệu.

### Xác minh tiếp theo — 25/11/2026

- Learn hiện dùng `StudyUtils.reviewQueue()` trong `prepareNextRound()`: thẻ đến
  hạn và thẻ mới được đưa vào lượt học, thẻ chưa đến hạn được giữ lại; **Ôn sớm**
  là lựa chọn riêng. Vì vậy ghi chú SRS ở phần phát hiện ban đầu bên dưới đã cũ.
- Scraper giữ `sourceWarning` trong manifest khi dùng lại bộ đã cache hoặc khi
  lần tải mới thất bại, tránh làm mất cảnh báo cho dữ liệu chưa được xác minh.
- Kiểm tra lại: unittest Python (7), Node (7), browser smoke và browser regressions
  (20) đều đạt trên môi trường hiện tại. Một lần chạy riêng từng báo lỗi kết nối
  khi từ chối POST cross-origin nhưng không tái hiện ở lần chạy lại hoặc 100 lần
  lặp của bài kiểm tra đó.

## Ưu tiên cao: dữ liệu và khả năng sử dụng

### 1. Lỗi đọc cloud bị coi là cloud rỗng, có thể ghi đè bản mới

- Vị trí: `index.html:3322–3340`, `index.html:4866–4898`.
- `getAllSets()` trả `[]` cả khi timeout/lỗi. Đồng bộ nền coi tất cả bộ thẻ local
  là chưa có trên cloud và gửi lên bằng `setDoc`, không kiểm tra phiên bản.
- Tái hiện: cho CloudDB giả lập trả `[]`; bộ local cũ được gửi tới `saveSet`.
- Hậu quả: một lần đọc lỗi có thể dẫn đến ghi đè nội dung mới trên cloud khi
  quyền ghi/kết nối hoạt động. Không kiểm chứng ghi đè trên dịch vụ thật.
- Cần sửa: phân biệt lỗi với danh sách rỗng; không ghi sau một lần đọc thất bại;
  có cơ chế phiên bản/xử lý xung đột.

### 2. Thay đổi từ thiết bị khác không cập nhật bộ thẻ đã tải

- Vị trí: `index.html:4881–4887`.
- Chỉ lưu cloud set khi ID chưa tồn tại local; bỏ qua mọi cập nhật cùng ID.
- Tái hiện: cloud trả cùng ID với tiêu đề mới và `updatedAt` lớn hơn, local vẫn
  giữ tiêu đề cũ.
- Hậu quả: thông báo “Đã đồng bộ” không bảo đảm nội dung hai máy giống nhau.
- Cần sửa: so sánh phiên bản nội dung và cập nhật có kiểm soát.

### 3. Một bộ thẻ cũ không hợp lệ làm kẹt cả trang chủ

- Vị trí: `index.html:4791–4805`, `index.html:6175–6215`.
- `normalizeSet()` ném lỗi trong vòng dựng danh sách, không được xử lý riêng
  từng bộ; hàm khởi tạo cũng không có xử lý lỗi ngoài cùng.
- Tái hiện: IndexedDB có một bộ cũ `cards: []`, reload → 0 thẻ trên dashboard,
  màn hình giữ “Đang tải danh sách học phần...”, có unhandled rejection.
- Cần sửa: cô lập bộ lỗi, hiển thị thao tác sửa/xuất/xóa và vẫn mở các bộ hợp lệ.

### 4. Nhập văn bản tự ý thay nội dung và bỏ dòng

- Vị trí: `index.html:4502–4517`.
- Tái hiện: `Ratio<TAB>x = 1: 2` được lưu thành định nghĩa `x - 1 - 2`.
  Dòng không nhận diện được dấu phân cách bị bỏ mà không thông báo.
- Hậu quả: công thức hoặc nội dung học bị thay đổi dù báo nhập thành công.
- Cần sửa: ưu tiên TAB nếu có, chỉ tách ở dấu phân cách đầu tiên và giữ nguyên
  phần định nghĩa; hiển thị dòng bị từ chối trước khi lưu.

### 5. Nhập lại bộ thẻ đã xóa: báo thành công nhưng không thể tìm thấy

- Vị trí: `index.html:4395–4413`, `index.html:4610–4617`,
  `index.html:4793`, `index.html:4826`.
- Tái hiện: tạo → xóa → nhập lại JSON cùng ID. Toast báo thành công nhưng
  dashboard không có bộ đó và ID vẫn nằm trong `qp_deleted_set_ids`.
- Cần sửa: thao tác nhập có chủ đích phải khôi phục ID khỏi danh sách đã xóa.

### 6. Tải bộ mới thất bại nhưng câu hỏi/nút thao tác vẫn thuộc bộ cũ

- Vị trí: `index.html:4920–4994`, `index.html:4997–5008`.
- Tái hiện: đang ở bộ A, chọn bộ B không tải được. Dropdown hiển thị B, nhưng
  `currentSet` và 4 nút đáp án còn hoạt động đều thuộc A.
- Hậu quả: người học nhầm nội dung; thao tác sửa/xóa có thể nhắm vào bộ khác
  với bộ đang hiển thị trên dropdown.
- Cần sửa: trạng thái loading/error rõ ràng và đồng bộ dropdown với dữ liệu;
  khóa các thao tác trên nội dung cũ trong lúc tải.

## Lỗi trải nghiệm đã tái hiện

### 7. Các nút sửa/reset/xuất/xóa bị khuất trên điện thoại

- Vị trí: `index.html:990–1007`, `index.html:2664–2672`.
- Chrome viewport 390px: mép phải nút sửa ở khoảng 431px, nút xóa ở 503px.
  Nhóm chọn bộ không xuống dòng, trong khi trang ẩn overflow ngang.
- Không tính các tab chế độ ra ngoài màn hình là lỗi: chúng có vùng cuộn ngang.
- Cần sửa: `min-width: 0` cho select, bố trí lại/cho xuống dòng nhóm thao tác.

### 8. Reload không khôi phục phiên Learn/Test đầy đủ

- Vị trí: `index.html:4085–4096`, `index.html:5200–5225`,
  `index.html:6181–6213`, `index.html:6837–6902`.
- Learn: trả lời câu đầu, đang ở câu 2 thì F5 → quay lại câu 1. `cardIndex`
  lưu trước khi tăng và không được sử dụng khi khôi phục; hàng đợi không lưu.
- Test: đã chọn 1 đáp án, F5 → 0 đáp án, tạo lại đề.
- Flashcards ở thứ tự thường đã qua kiểm thử, không có nghĩa mọi mode đều
  khôi phục đúng.
- Cần sửa: lưu queue/câu hỏi/đáp án và con trỏ phiên, kiểm tra nội dung bộ thẻ
  trước khi khôi phục.

### 9. Reset trên thanh công cụ làm mất sao sau reload

- Vị trí: `index.html:4707–4727` so với `index.html:5940–5949`.
- Tái hiện: gắn sao → reset tiến độ bằng thanh công cụ → sao vẫn hiển thị;
  reload → sao biến mất.
- Nguyên nhân: xóa toàn bộ progress trong DB nhưng không xóa hoặc lưu lại sao
  trong trạng thái giao diện. Nút reset trong Settings có hành vi khác.
- Cần sửa: thống nhất ý nghĩa reset và giữ trạng thái sao nhất quán.

### 10. “Tôi đã trả lời đúng” nâng thẻ chưa học lên thẳng thành thạo

- Vị trí: `index.html:5452–5457`, `index.html:5546–5552`.
- Tái hiện: thẻ mastery 0 → trả lời bị chấm sai → bấm override → mastery 2.
  Trả lời đúng bình thường ở cùng trạng thái chỉ lên mastery 1.
- Nguyên nhân: demote đặt mastery 1; override tăng tiếp thay vì phục hồi trạng
  thái trước câu trả lời rồi chấm lại.

### 11. Cho lưu thẻ có đáp án rỗng nhưng Write không thể chấm đúng

- Vị trí: `js/study-utils.js:19–23`, `index.html:5387–5390`.
- Tái hiện: nhập `{term: "question", definition: ""}` → mở Write → đáp án
  đúng là chuỗi rỗng, nhưng submit không nhận câu trả lời rỗng.
- Cần sửa: kiểm tra đủ hai mặt cho chế độ hỏi đáp hoặc loại thẻ thiếu mặt khỏi
  chế độ không tương thích.

### 12. Bookmarklet trong Nhập nhanh bị lỗi cú pháp

- Vị trí: `index.html:3754–3759`.
- Chuỗi JavaScript có newline thật trong dấu nháy đơn. Biên dịch nội dung
  `javascript:` trong trình duyệt trả `Invalid or unexpected token`.
- Bookmarklet thứ hai ở `index.html:3962` không mắc lỗi cú pháp này.
- Cần sửa: dùng một nguồn bookmarklet chung, escape newline và kiểm tra
  destination thay vì duy trì hai đoạn mã riêng.

### 13. Khi Firebase SDK không tải được, nút Cloud gọi hàm không tồn tại

- Vị trí: `index.html:3227–3285`.
- Tái hiện khi chặn HTTPS: `typeof showCloudStatusHelp === "undefined"`.
- Module import SDK lỗi trước khi khai báo hàm trợ giúp; nhãn cloud cũng không
  chuyển sang trạng thái lưu trên máy.
- Cần sửa: UI trợ giúp/fallback độc lập với tải SDK.

### 14. Khóa progress có thể trùng giữa hai bộ thẻ

- Vị trí: `js/database.js:170–173`.
- `_getProgressId('a_b', 'c') === _getProgressId('a', 'b_c')`.
- Các chuỗi ID này đều được phép dùng. Thẻ thuộc hai bộ có thể ghi đè tiến độ.
- Cần sửa: khóa tổ hợp không nhập nhằng, kèm migration dữ liệu cũ.

### 15. Modal chưa giữ focus bàn phím bên trong

- Vị trí: `js/navigation.js:117–128`.
- Tái hiện: mở Nhập nhanh, focus nút cuối, Tab → focus ra BODY/nội dung nền.
- `aria-modal` không tự khóa focus; cũng chưa có phục hồi focus về nút mở.
- Cần sửa: quản lý focus, inert nội dung nền, hỗ trợ Escape và trả focus.

## Những hạn chế/điểm khác cần xử lý

- **Dữ liệu mẫu:** 2.712 dòng trong 20 bộ, chỉ 1.512 ID duy nhất tính trong
  từng bộ, tức 1.200 dòng lặp ở 9 bộ. Bỏ bản sao lúc mở không khôi phục được
  nội dung chưa tải. Cần đối chiếu nguồn Quizlet để kết luận số thẻ còn thiếu.
- **SRS:** UI Learn không gọi `getNextCardsForLearn`, không dùng `nextReview`.
  Hiện đây là luyện theo vòng/mức thành thạo, chưa phải lịch ôn cách quãng đầy đủ.
- **Cloud dùng chung:** client không có đăng nhập/phân quyền theo chủ bộ thẻ;
  thao tác xóa gọi `deleteDoc` trên collection chung. Quyền thực tế phụ thuộc
  Firestore Rules chưa được kiểm tra. Script `scripts/push_sets_to_firebase.py:102–114`
  vẫn hướng dẫn mở quyền đọc/ghi công khai, không nhất quán với hướng dẫn UI.
- **Server local:** bind mọi interface (`server.py:442`), CORS `*`, API nhập
  cho ghi lại ID có sẵn. Cần xác định rõ chế độ dùng riêng hay chia sẻ LAN,
  rồi giới hạn quyền ghi tương ứng.
- **Khởi động:** `start.sh:17–24` chờ tối đa khoảng 2 giây rồi vẫn mở trình
  duyệt dù server chưa sẵn sàng; `open` chỉ phù hợp macOS.
- **Bản nháp:** chưa lưu bản nháp khi tạo/sửa thẻ; refresh hoặc rời màn hình
  có thể mất nội dung chưa lưu.
- **Offline:** chưa có service worker/cache ứng dụng; dữ liệu trong IndexedDB
  không bảo đảm tải lại trang web được khi mất mạng.
- **Xuất file:** đã có tải JSON nhưng chưa có input chọn file để nhập lại;
  người dùng phải mở file và copy nội dung. Thông báo đã sao chép xuất hiện
  trước khi Promise clipboard thành công (`index.html:4594–4599`).

## Thứ tự khắc phục đề xuất

1. Cloud/xung đột dữ liệu, lỗi khởi tạo, nhập sai nội dung, nhập lại sau xóa.
2. Đồng bộ trạng thái khi đổi bộ, các nút mobile, lưu phiên Learn/Test.
3. Reset/override/đáp án rỗng, bookmarklet, fallback offline, focus modal.
4. Đối chiếu dữ liệu mẫu, tích hợp SRS thật và xác định mô hình tài khoản/cloud.
