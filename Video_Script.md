# Kịch bản video demo — Griductive Solver (≈ 8 phút)

Đề bài (mục 4.7) chấm 10 điểm:
- **Giao diện (5 điểm).**
- **Tính năng (5 điểm):** chơi tay và chạy solver (chọn màn, chạy, xem lời giải).

Yêu cầu khác của đề: video dài 5–10 phút, có **thuyết minh hoặc phụ đề** tiếng Việt hay tiếng Anh, nộp **link Google Drive** (không dùng YouTube).

---

## 0. Chuẩn bị trước khi quay

1. Mở terminal và chạy:
   ```bash
   cd Source
   python3 main.py
   ```
   Trình duyệt tự mở `http://127.0.0.1:8765`.
2. Phóng to trình duyệt toàn màn hình. Nên đặt zoom 110–125% để chữ đọc được trong video.
3. Chọn chế độ tối, bấm nút mặt trăng ở góc phải.
4. Để sẵn một terminal thứ hai, đang đứng trong thư mục `Source/`, cho phần 4.
5. Tập trước một lượt. Các nước đi bên dưới dùng câu đố **`05-4x4-a` (The Ember Gallery)**.
6. Quay bằng QuickTime (File → New Screen Recording) hoặc OBS, và thu tiếng micro.

Hai đường link giúp vào nhanh trạng thái mong muốn nếu cần quay lại một cảnh:
- `http://127.0.0.1:8765/?case=05-4x4-a` mở thẳng câu đố.
- `…&steps=6&select=A1` cho agent đi sẵn 6 bước và làm nổi bật manh mối A1.

---

## Phần 1 — Giao diện (≈ 1 phút 30) · *5 điểm GUI*

| Thao tác | Lời thoại gợi ý |
|---|---|
| Mở trang, để yên 2 giây | "Đây là Casebook, phiên bản Griductive của nhóm: mỗi cầu thủ bí mật bị **Red card** (tương ứng Criminal) hoặc **Fair play** (Innocent). Chỉ được kết luận khi có thể **chứng minh logic**, không được đoán." |
| Rê chuột qua lưới | "Lưới có tọa độ cột A–D và hàng 1–4. Thẻ úp hiện ảnh, tên, vị trí và đội tuyển của cầu thủ. Thẻ có dấu ★ là thẻ lật sẵn từ đầu." |
| Rê qua thanh trên cùng | "Phía trên là tên vụ án, số người đã xác định, số lỗi và số lần gọi SAT solver." |
| Rê qua cột trái | "Cột trái có danh sách 12 câu đố (3×3, 4×4, 5×5 và 2 ca lỗi), nút Load, Open file, và nút New để sinh câu đố mới; sau đó là Restart, Hint, và phần Logic agent gồm Step, Auto solve, thanh chỉnh tốc độ." |
| Rê qua cột phải | "Cột phải có ba tab: Clues (các manh mối đã lật), Trace (lịch sử nước đi và truy vấn SAT) và Solver (thống kê bộ giải)." |
| Bấm nút sáng/tối 2 lần | "Giao diện có chế độ sáng và tối." |

---

## Phần 2 — Chơi tay (≈ 2 phút 30) · *chơi thủ công*

Đang ở câu đố `05-4x4-a`. Thẻ lật sẵn là **Courtois (A1)**.

| # | Thao tác | Kết quả trên màn hình | Lời thoại gợi ý |
|---|---|---|---|
| 1 | Ở tab Clues, bấm manh mối của Courtois | 4 góc được viền sáng | "Manh mối đầu tiên: *At least 4 fair-play players in the corners*. Bấm vào manh mối thì các ô nó đếm được tô sáng: chính là 4 góc." |
| 2 | Bấm thẻ **Haaland (B1)** → chọn **Red card** | Thẻ rung, thông báo *Not provable yet* | "Nếu đoán bừa Haaland bị thẻ đỏ, game từ chối với **NOT_PROVABLE**: các manh mối chưa đủ để chứng minh. Đây chỉ là cảnh báo và tính một lỗi." |
| 3 | Bấm **Kimmich (D1)** → **Fair play** | Thẻ lật, lộ manh mối mới | "Bốn góc có ít nhất 4 người Fair play, mà bàn chỉ có 4 góc, nên cả bốn đều Fair play. Kimmich ở góc D1 được chấp nhận, thẻ lật ra và lộ thêm manh mối." |
| 4 | **Son (A4)** → Fair play, rồi **Vinícius (D4)** → Fair play | Lộ thêm 2 manh mối | "Tương tự cho Son và Vinícius." |
| 5 | Đọc manh mối của Vinícius | *Exactly 2 red-carded players in Salah and Tiến Linh* | "Manh mối của Vinícius nói trong hai người Salah và Tiến Linh có đúng 2 người bị thẻ đỏ, tức là cả hai." |
| 6 | Bấm **Hint (H)** | Banner gợi ý và các manh mối hỗ trợ được tô | "Nút Hint chỉ ra một người chứng minh được ngay, kèm **tập manh mối tối thiểu** dùng để chứng minh. Hint không đọc đáp án ẩn." |
| 7 | **Salah (D3)** → **Red card** | Được chấp nhận | "Salah bị thẻ đỏ, đúng như suy luận." |
| 8 | **Tiến Linh (B4)** → chọn **Fair play** (cố tình sai) | Màn hình **Game over** | "Còn nếu chọn **ngược** với điều đã chứng minh, game báo **CONTRADICTED** và kết thúc ván. Thông báo cho biết các manh mối chứng minh Tiến Linh bị thẻ đỏ. Game không lật thẻ, không lộ thêm manh mối nào." |
| 9 | Bấm **Restart case** | Bàn trở về trạng thái đầu | "Restart để chơi lại từ đầu." |

---

## Phần 3 — Chạy solver (≈ 3 phút) · *chạy bộ giải, xem lời giải*

| # | Thao tác | Lời thoại gợi ý |
|---|---|---|
| 1 | Bật **Show solver deductions** | "Mỗi thẻ úp hiện kết quả phân loại: *forced red card*, *forced fair play* hoặc *unknown*. Với mỗi người i, solver kiểm tra hai công thức: nếu KB ∧ ¬Cᵢ **UNSAT** thì i chắc chắn bị thẻ đỏ; nếu KB ∧ Cᵢ **UNSAT** thì chắc chắn Fair play; cả hai SAT thì chưa biết." |
| 2 | Bấm **Step (N)** 2–3 lần, mở tab **Trace**, bấm "SAT queries" ở một bước | "Mỗi bước, agent chọn người bị ép **đầu tiên theo thứ tự hàng** rồi nộp phán đoán. Trace ghi số bước, các manh mối đang dùng, từng truy vấn SAT như `KB ∧ C(A2) → UNSAT`, và manh mối mới lộ ra." |
| 3 | Bấm **Auto solve (A)** | "Auto solve lặp lại cho tới hết. Màn **Case closed** cho thấy agent giải xong mà không đoán và không sai lần nào." |
| 4 | Bấm **Admire the board**, mở tab **Solver** | "Tab Solver cho thấy kích thước cơ sở tri thức: số biến chính, biến phụ và mệnh đề CNF, cùng thống kê DPLL: số lần quyết định, lan truyền, quay lui, xung đột." |
| 5 | Đổi *Cardinality encoding* sang **Unary counter** | "Đổi cách mã hóa ràng buộc đếm sang bộ đếm tuần tự: số biến phụ và mệnh đề tăng lên, nhưng kết quả suy luận không đổi." |
| 6 | Bấm **Check uniqueness of full clue set** | "Kiểm tra trên **toàn bộ** manh mối: tìm một lời giải, thêm mệnh đề chặn rồi giải lại. Kết quả UNSAT nên câu đố có **đúng một lời giải** (UNIQUE)." |
| 7 | Load **`10-5x5-b`**, kéo tốc độ nhanh nhất, Auto solve | "Bàn 5×5 lớn hơn: 25 biến chính và vài trăm biến phụ, vẫn giải trong khoảng nửa giây." |
| 8 | Load **`90-3x3-ambiguous`**, Auto solve | "Ca lỗi thứ nhất có nhiều lời giải. Agent dừng ở **STUCK** vì không ai bị ép, và **từ chối đoán**." |
| 9 | Load **`91-3x3-inconsistent`**, Auto solve | "Ca lỗi thứ hai có manh mối mâu thuẫn. KB trở thành UNSAT nên agent báo **INCONSISTENT**." |
| 10 | Chọn 4×4, bấm **New**, rồi Auto solve | "Bộ sinh câu đố tạo màn mới, bảo đảm giải được hoàn toàn bằng suy luận." |

---

## Phần 4 — Terminal (≈ 1 phút, có thể bỏ nếu thiếu thời gian)

```bash
python3 main.py --solve puzzles/01-3x3-a.json -v   # agent giải trong terminal, in toàn bộ trace
python3 main.py --check puzzles/05-4x4-a.json      # kiểm tra nghiệm duy nhất
python3 -m unittest discover -s tests              # bộ kiểm thử
```

Lời thoại gợi ý: "Có thể chạy cùng logic từ dòng lệnh: trace in đủ từng truy vấn SAT. Bộ kiểm thử so sánh bộ mã hóa CNF với bộ đánh giá ngữ nghĩa, và so sánh DPLL với vét cạn; tất cả đều pass. Kết quả thực nghiệm trên 12 câu đố với 3 cấu hình có trong báo cáo."

---

## Câu chốt (≈ 15 giây)

"Mọi phán đoán đều là **hệ quả logic** của các manh mối đã lật, được kiểm tra bằng DPLL do nhóm tự cài đặt. Agent chỉ nhìn thấy thông tin công khai, không bao giờ xem đáp án ẩn và không bao giờ đoán."

---

## Sau khi quay

1. Xuất video MP4 và kiểm tra thời lượng nằm trong 5–10 phút, tiếng rõ.
2. Upload lên **Google Drive** → Share → **General access: Anyone with the link → Viewer**.
3. Mở link trong **cửa sổ ẩn danh** để chắc người khác xem được.
4. Dán link vào báo cáo: trong `report_latex/main.tex`, tìm dòng `Dán link Google Drive của video demo` và thay bằng `\url{<link>}`. Sau đó build lại PDF:
   ```bash
   python3 report_latex/gen_data.py
   cd report_latex && tectonic -X compile main.tex --outdir build
   ```
