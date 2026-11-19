# Kịch bản video demo (5–10 phút)

> Quay màn hình kèm thuyết minh tiếng Việt (hoặc phụ đề). Upload lên **Google Drive**, đặt quyền
> *Anyone with the link → Viewer*, mở thử bằng cửa sổ ẩn danh, rồi dán link vào trang bìa của báo cáo
> (`report_src/build_report.py`, tìm `[dán link Google Drive…]`, sau đó chạy lại `python3 report_src/build_report.py`).
> **Không** dùng link YouTube.

## Phần 1: Giao diện (≈ 2 phút, 5 điểm)

1. Mở terminal: `cd Source && python3 main.py`. Trình duyệt tự mở `http://127.0.0.1:8765`.
2. Giới thiệu bố cục:
   - **Thanh trên cùng**: tên case, số người đã xác định, số lỗi, số lần gọi SAT, nút sáng/tối.
   - **Cột trái**: danh sách case (3×3, 4×4, 5×5, 2 ca lỗi), Load, Open file, sinh puzzle mới (New), Restart, Hint,
     Logic agent (Step, Auto solve, chỉnh tốc độ, bật “Show solver deductions”), chú thích màu và phím tắt.
   - **Giữa**: lưới có tọa độ cột A–D và hàng 1–4. Thẻ úp có avatar, tên, nghề. Thẻ ★ là thẻ lật sẵn từ đầu.
   - **Cột phải**: tab Clues, Trace và Solver.
3. Bấm nút mặt trời/mặt trăng để chuyển theme sáng/tối.

## Phần 2: Chơi tay (≈ 3 phút)

1. Load case `05-4x4-a` (The Ember Gallery).
2. Bấm clue của Ada ở tab Clues: 4 góc được tô viền liền. Giải thích đây là các ô được clue đếm.
3. Chọn một người **chưa chứng minh được**, bấm Criminal. Thẻ rung, báo **NOT_PROVABLE**, không lộ clue nào.
4. Bấm **Hint (H)**: banner chỉ ra người có thể chứng minh, kèm các clue tối thiểu cần dùng (viền cam). Bấm “Show the verdict”.
5. Chọn sai chiều cho người đó (ví dụ Criminal trong khi phải là Innocent). Màn hình báo **CONTRADICTED**.
6. Chọn đúng. Thẻ lật 3D, có viền màu trạng thái và clue mới. Toast báo “Correct”.
7. Đi thêm 2–3 bước. Mở tab **Trace** để xem nước đi của người chơi.

## Phần 3: Chạy solver (≈ 3 phút)

1. Bật **Show solver deductions**: các thẻ úp hiện “forced criminal / forced innocent / unknown”. Giải thích đây là kết quả kiểm tra
   KB ∧ ¬C<sub>i</sub> / KB ∧ C<sub>i</sub> bằng DPLL.
2. Bấm **Step (N)** vài lần. Ở tab Trace, mở “SAT queries” để thấy từng truy vấn `KB ∧ ¬C(B2) → UNSAT`, các clue đang dùng
   và clue mới lộ ra.
3. Bấm **Auto solve (A)**. Agent tự giải tới khi “Case closed”, hiện thống kê số verdict và số lần gọi SAT.
4. Mở tab **Solver**: số biến chính, biến phụ, mệnh đề; thống kê DPLL; đổi cách mã hóa sang *Unary counter* thì số biến phụ và mệnh đề tăng.
   Bấm **Check uniqueness**: kết quả UNIQUE.
5. Load `10-5x5-b` (5×5), chạy Auto solve với tốc độ nhanh nhất.
6. Load ca lỗi `90-3x3-ambiguous`, bấm Auto solve. Agent dừng ở **STUCK** và từ chối đoán. Uniqueness báo **MULTIPLE**.
7. Load `91-3x3-inconsistent`, bấm Auto solve. Agent báo **INCONSISTENT**.
8. (Tùy chọn) Chọn 3×3, bấm **New** để sinh puzzle mới, rồi chạy Auto solve.
9. (Tùy chọn) Ở terminal: `python3 main.py --solve puzzles/05-4x4-a.json -v` và `python3 experiments.py`.

## Câu chốt

“Mọi kết luận đều là hệ quả logic của các clue đã lật. Agent không bao giờ xem lời giải ẩn và không bao giờ đoán.”
