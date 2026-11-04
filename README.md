# Griductive Solver

Đồ án Cơ sở AI

---

## 1. Giới thiệu tổng quan
**Griductive** là trò chơi suy luận dạng lưới (grid-deduction game) trên bảng kích thước $N \times N$ (với $N \in \{3, 4, 5\}$). Mỗi ô trên bảng chứa một nhân vật có trạng thái bí mật là **Criminal** hoặc **Innocent**, kèm theo một manh mối logic có cấu trúc.

Quy tắc cốt lõi: **TUYỆT ĐỐI KHÔNG ĐƯỢC ĐOÁN (NO GUESS)**. Một phán đoán chỉ được chấp nhận khi nó là hệ quả logic bắt buộc ($\models$) từ Knowledge Base hiện tại ($KB_t$).

Hệ thống được xây dựng hoàn toàn bằng **Python thuần** (sử dụng thư viện đồ họa chuẩn `tkinter`), tự triển khai thuật toán giải SAT **DPLL**, bộ mã hóa logic mệnh đề sang dạng chuẩn **CNF**, và tác tử suy luận diễn dịch **Logic Agent** đảm bảo nguyên tắc bảo mật thông tin.

---

## 2. Cấu trúc thư mục `Source`
Mã nguồn được tái cấu trúc thành kiến trúc phân lớp chuyên nghiệp, rõ ràng và có tính module hóa cao:

```text
Source/
├── main.py                     # Điểm khởi chạy ứng dụng GUI
├── experiments.py              # Script chạy đánh giá thực nghiệm (xuất CSV)
├── experiment_results.csv      # Bảng kết quả thực nghiệm chi tiết
├── requirements.txt            # Thông tin môi trường thực thi (Python 3.10+)
├── README.md                   # Tài liệu hướng dẫn sử dụng và báo cáo kỹ thuật
├── assets/                     # Tài nguyên đồ họa (tranh chân dung 25 nhân vật)
│   └── suspect_portraits.png
├── core/                       # Package chứa toàn bộ logic toán học & thuật toán
│   ├── __init__.py
│   ├── models.py               # Định nghĩa các Data Model (Character, Clue, Puzzle,...)
│   ├── regions.py              # Xử lý các vùng (Row, Column, Neighbors, Explicit,...)
│   ├── clues.py                # Định nghĩa ngữ nghĩa, validation, mô tả và Direct Semantic Evaluator
│   ├── cnf.py                  # Bộ mã hóa mệnh đề sang CNF (hỗ trợ biến chính & phụ)
│   ├── dpll.py                 # Bộ giải SAT DPLL tự cài đặt (đầy đủ các bước chuẩn)
│   ├── agent.py                # Tác tử suy luận LogicAgent (chỉ truy cập PublicState)
│   ├── engine.py               # GameEngine quản lý game, kiểm tra nghiệm duy nhất
│   ├── puzzle_generator.py     # Trình tạo màn chơi ngẫu nhiên, giải tuần tự không đoán
│   └── puzzle_io.py            # Chức năng Lưu/Đọc màn chơi từ file JSON (phục vụ Load)
├── gui/                        # Package giao diện người dùng Desktop (Tkinter)
│   ├── __init__.py
│   ├── theme.py                # Bảng màu thẩm mỹ, typography và styling
│   ├── board_view.py           # Component hiển thị lưới thẻ nhân vật, chân dung, highlight
│   ├── sidebar_view.py         # Component thanh điều khiển, verdict buttons, metrics, trace
│   └── app.py                  # Window Controller điều phối Board, Sidebar, Engine và Agent
├── puzzles/                    # Bộ puzzle mẫu chuẩn JSON để kiểm tra tính năng Load
│   ├── sample_3x3.json
│   ├── sample_3x4.json
│   ├── sample_4x4.json
│   └── sample_5x5.json
└── tests/                      # Bộ kiểm thử tự động toàn diện (Unit Tests)
    ├── __init__.py
    ├── test_dpll.py            # Kiểm thử DPLL solver trên SAT, UNSAT, unit propagation
    ├── test_cnf_semantics.py   # Kiểm thử đối chiếu 100% giữa CNF và Direct Semantic Evaluator
    ├── test_agent_engine.py    # Kiểm thử tính bảo mật của state, submit feedback, auto-step
    └── test_puzzles.py         # Kiểm thử tính duy nhất (uniqueness) và round-trip JSON
```

---

## 3. Hướng dẫn cài đặt và sử dụng

### 3.1 Yêu cầu hệ thống
- **Python 3.10** trở lên.
- Đã cài đặt `tkinter` (mặc định có sẵn trong bộ cài Python trên Windows/macOS).
- Không yêu cầu cài đặt thêm bất kỳ thư viện bên ngoài (external packages) nào!

### 3.2 Khởi chạy giao diện trò chơi (GUI)
Từ thư mục `Source`, chạy lệnh:
```bash
python main.py
```
*(Nếu trên Linux/macOS dùng `python3 main.py`)*

### 3.3 Hướng dẫn thao tác trên GUI
1. **Khám phá bảng chơi:** Các thẻ mở sẵn ban đầu sẽ hiển thị trạng thái `CRIMINAL` (nền đỏ) hoặc `INNOCENT` (nền xanh) kèm theo manh mối logic được mở.
2. **Highlight Manh mối (Spotlight):** Nhấp chuột vào một thẻ **đã giải** bất kỳ để kích hoạt hiệu ứng:
   - Viền vàng: Thẻ chủ sở hữu manh mối.
   - Viền xanh dương: Các ô/nhân vật được manh mối đó nhắc tới hoặc đếm trong vùng.
3. **Phán đoán nhân vật (Submit Verdict):**
   - Nhấp chuột vào một thẻ **chưa giải** (úp mặt). Ô sẽ sáng viền xanh đậm.
   - Bấm nút **CRIMINAL** hoặc **INNOCENT** trên thanh Sidebar.
   - Nếu kết luận đã được chứng minh: Trạng thái hiển thị `ACCEPTED`, thẻ lập tức lật lên và hé lộ manh mối mới!
   - Nếu kết luận chưa thể chứng minh: Hệ thống báo `NOT_PROVABLE` và giữ nguyên trạng thái.
   - Nếu chọn ngược với kết luận bắt buộc: Hệ thống báo `CONTRADICTED`.
4. **Các nút điều khiển:**
   - **Load...:** Mở hộp thoại tải màn chơi từ file JSON (trong thư mục `puzzles/` hoặc bất kỳ file nào).
   - **New Random:** Mở hộp thoại chọn kích thước (3x3, 3x4, 4x4, 5x5) và sinh ván chơi ngẫu nhiên mới.
   - **Restart:** Bắt đầu lại ván chơi hiện tại về 2 thẻ ban đầu.
   - **Hint:** Tự động tìm kiếm và chỉ ra thẻ có thể chứng minh tiếp theo mà hoàn toàn không xem trộm đáp án ẩn.
   - **Auto Step:** Yêu cầu Logic Agent tự động chứng minh 1 bước tiếp theo.
   - **Auto Solve:** Kích hoạt chế độ giải tự động tuần tự với hiệu ứng hoạt họa lật thẻ trực quan.
5. **Deduction Trace & Metrics:**
   - Bảng bên phải hiển thị chi tiết số biến chính ($C_i$), số biến phụ, số mệnh đề CNF, số lần gọi SAT, decisions, propagations, backtracks, và runtime.
   - Khung nhật ký ghi lại từng bước suy luận theo đúng định dạng yêu cầu của đề bài.

---

## 4. Chạy kiểm thử tự động (Unit Tests)
Từ thư mục `Source`, thực hiện lệnh kiểm thử toàn diện:
```bash
python -m unittest discover -s tests -t . -v
```
Toàn bộ 18 test cases kiểm tra:
- Thuật toán giải SAT DPLL (SAT, UNSAT, Assumptions, Conflict detection, Unit propagation chain).
- Sự tương đồng ngữ nghĩa giữa CNF Encoding và Direct Semantic Evaluator trên tất cả các mẫu manh mối.
- Bảo mật thông tin của Logic Agent (không chứa `solution` hoặc manh mối chưa mở).
- Tính duy nhất của nghiệm (Uniqueness check) trên các kích thước 3x3 đến 5x5.
- Đọc/ghi JSON của Puzzle.

---

## 5. Chạy đánh giá thực nghiệm (Benchmark Experiments)
Từ thư mục `Source`, thực hiện:
```bash
python experiments.py
```
Kết quả thực nghiệm sẽ được ghi tự động vào file `experiment_results.csv` với đầy đủ các trường thông tin:
- Tên ván chơi & Kích thước bảng ($3\times 3, 3\times 4, 4\times 4, 5\times 5$).
- Số biến chính (`primary_variables`) và biến phụ (`auxiliary_variables`).
- Số mệnh đề CNF khởi tạo (`initial_clauses`).
- Tổng số lần gọi SAT Solver (`sat_calls`).
- Số quyết định (`decisions`), lan truyền đơn vị (`propagations`), quay lui (`backtracks`).
- Số bước suy luận diễn dịch (`deduction_steps`).
- Tổng thời gian thực thi (`total_runtime_ms`).