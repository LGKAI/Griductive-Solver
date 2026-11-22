# Casebook — Bộ Giải Trò Chơi Suy Luận Griductive (CSC14003 Project 2)

Casebook cài đặt hoàn chỉnh trò chơi suy luận **Griductive** kết hợp tác tử logic **không đoán mò** (*no-guess*), sử dụng logic mệnh đề, bộ mã hóa CNF tự động và bộ giải SAT **DPLL** tự viết từ đầu.

## Yêu cầu hệ thống

- **Python 3.10 trở lên** (phát triển và kiểm thử trên Python 3.12 / 3.14).
- **Không cần thư viện bên thứ ba**: toàn bộ mã nguồn chỉ dùng thư viện chuẩn Python (xem `requirements.txt`).
- Trình duyệt web hiện đại bất kỳ (Chrome, Edge, Firefox hoặc Safari) để chạy giao diện.

## Hướng dẫn chạy chương trình

Mở terminal tại thư mục `Source`:

```bash
# Chạy giao diện web cục bộ (tự mở http://127.0.0.1:8765)
python main.py

# Tùy chọn cổng khác và không tự mở trình duyệt
python main.py --port 9000 --no-browser
```

*(Lưu ý: trên macOS/Linux có thể dùng `python3` thay cho `python`.)* Nếu cổng `8765` đang bận, chương trình tự động chọn cổng trống kế tiếp. Nhấn `Ctrl+C` để dừng máy chủ.

Các công cụ dòng lệnh (CLI):

```bash
# Tác tử giải trực tiếp trên terminal và in toàn bộ nhật ký suy luận (trace)
python main.py --solve puzzles/05-4x4-a.json -v

# Giải với chiến lược 'naive' và bộ mã hóa đếm 'counter'
python main.py --solve puzzles/05-4x4-a.json --strategy naive --cardinality counter

# Kiểm tra tính duy nhất của nghiệm trên toàn bộ manh mối
python main.py --check puzzles/05-4x4-a.json

# Chạy toàn bộ thực nghiệm benchmark -> lưu vào results/ (CSV, JSON, Markdown, biểu đồ SVG)
python experiments.py

# Chạy nhanh với cấu hình mặc định -> lưu vào results/quick/
python experiments.py --quick

# Chạy toàn bộ bộ kiểm thử tự động (41 unit & integration tests)
python -m unittest discover -s tests -v

# Tạo lại bộ câu đố mẫu trong puzzles/ (seed cố định)
python tools/build_puzzles.py
```

## Hướng dẫn sử dụng giao diện Web (Casebook)

| Thành phần | Chức năng |
|---|---|
| **Case files / Load** | Chọn một vụ án có sẵn trong danh sách và nạp vào bàn chơi (hỗ trợ nhấp đúp chuột). |
| **Open file** | Tải tệp câu đố định dạng JSON từ máy tính (xem cấu trúc bên dưới). |
| **New (3×3 / 4×4 / 5×5)** | Sinh ngẫu nhiên một màn chơi mới bảo đảm giải được hoàn toàn bằng suy luận, không cần đoán. |
| **Bộ nhân vật cầu thủ** | Mặc định hiển thị 30 ngôi sao bóng đá trong màu áo đội tuyển (gồm cả các tuyển thủ Việt Nam), ảnh từ Wikimedia Commons (`web/portraits/CREDITS.md`). Hai trạng thái hiển thị là **Red card** (tương ứng *Criminal*) và **Fair play** (tương ứng *Innocent*). Đây chỉ là lớp hiển thị: bàn chơi lớn hơn 30 ô sẽ giữ nguyên tên trong tệp JSON. |
| **Nhấp thẻ đang úp** | Đưa ra phán đoán cho nhân vật: **Criminal / Red card** (`C`) hoặc **Innocent / Fair play** (`I`). |
| **Restart** (`R`) | Đặt lại màn chơi về trạng thái ban đầu (phím `R` sẽ hỏi xác nhận nếu đang có tiến trình). |
| **Hint** (`H`) | Chỉ ra một nhân vật có thể chứng minh ngay lúc này và làm nổi bật tập manh mối tối thiểu dùng để suy luận (chỉ hiện đáp án khi bạn bấm xem). |
| **Step** (`N`) / **Auto solve** (`A`) | Cho tác tử logic đi từng bước hoặc tự động giải đến khi hoàn tất / bế tắc. Thanh trượt điều chỉnh tốc độ giải. |
| **Nhấp manh mối đã mở** | Chiếu sáng các ô được đếm (viền nét liền) và các nhân vật được nhắc tên (viền nét đứt). Nhấn `Esc` để tắt. |
| **Show solver deductions** | Hiển thị lớp phủ kết quả phân tích kéo theo hiện tại (bắt buộc tội phạm / vô tội / chưa xác định) lên các thẻ chưa lật. |
| **Tab Trace** | Liệt kê từng bước đi của người chơi và tác tử cùng các truy vấn SAT (ví dụ `KB ∧ ¬C(B2) -> UNSAT`), manh mối đang kích hoạt và manh mối mới mở. |
| **Tab Solver** | Theo dõi kích thước Cơ sở tri thức (biến chính, biến phụ, số mệnh đề), thống kê DPLL, đổi chiến lược truy vấn / chế độ mã hóa đếm và chạy kiểm tra nghiệm duy nhất. |

Nếu phán đoán không hợp lệ, Engine từ chối và trả về `NOT_PROVABLE` (chưa đủ dữ kiện ép buộc) hoặc `CONTRADICTED` (logic chứng minh điều ngược lại) mà không làm lộ bất kỳ thông tin ẩn nào.

## Thêm hoặc thay ảnh chân dung cầu thủ

Mỗi cầu thủ hiển thị ảnh tại `web/portraits/football/<slug>.jpg` (ví dụ `Văn Hậu` -> `van-hau.jpg`), hoặc tự vẽ avatar SVG áo đấu nếu thiếu ảnh. Trên macOS (`sips`), có thể cắt và cài đặt ảnh mới bằng lệnh:

```bash
python tools/add_portrait.py football Messi ~/Downloads/messi.jpg --center 0.5 0.25 --size 0.7 --source https://...
```

Trong đó `--center X Y` là tâm vùng cắt theo tỉ lệ ảnh (mặc định `0.5 0.3`), `--size` là độ dài cạnh hình vuông cắt theo cạnh ngắn của ảnh. Khởi động lại `main.py` sau khi cập nhật ảnh.

## Kiến trúc mã nguồn

```text
Source/
├── main.py                  Điểm khởi chạy chính: máy chủ GUI web và CLI (--solve, --check)
├── experiments.py           Chạy thực nghiệm benchmark toàn bộ cấu hình -> xuất ra results/
├── requirements.txt         Ghi chú phiên bản Python & thông tin không dùng gói ngoài
├── griductive/
│   ├── board.py             Hình học lưới và phân giải biểu thức vùng (hàng, cột, lân cận + mở rộng)
│   ├── clues.py             Ngôn ngữ manh mối: kiểm tra hợp lệ, đánh giá ngữ nghĩa trực tiếp, mô tả văn bản
│   ├── cnf.py               Ánh xạ biến, bộ dựng CNF, cổng Tseitin, mã hóa đếm và ClueEncoder
│   ├── dpll.py              Bộ giải SAT DPLL tự cài đặt (lan truyền đơn vị, quay lui, thống kê)
│   ├── knowledge.py         PublicState (tri thức công khai cho Agent) và dựng cơ sở tri thức KB_t
│   ├── entailment.py        Phân loại CRIMINAL / INNOCENT / UNKNOWN / INCONSISTENT, Hint tối thiểu, kiểm tra duy nhất
│   ├── engine.py            GameEngine: nắm giữ lời giải ẩn, thẩm định phán đoán, lật thẻ
│   ├── agent.py             LogicAgent: vòng lặp suy diễn tự động và ghi nhật ký trace
│   ├── generator.py         Bộ sinh câu đố ngẫu nhiên bảo đảm giải được không đoán mò
│   ├── puzzle.py            Định dạng tệp câu đố JSON và kiểm tra tính toàn vẹn dữ liệu
│   ├── themes.py            Chủ đề nhân vật cầu thủ (tên, ảnh, áo đấu) và nhãn trạng thái hiển thị
│   └── server.py            Máy chủ HTTP JSON cục bộ cho giao diện web (chỉ dùng thư viện chuẩn)
├── web/                     Giao diện frontend HTML, CSS, JavaScript thuần (không cần build)
├── puzzles/                 Bộ 12 câu đố mẫu (3×3, 4×4, 5×5 cùng 2 ca lỗi mơ hồ / mâu thuẫn)
├── results/                 Kết quả thực nghiệm (CSV, JSON, Markdown và biểu đồ SVG)
├── tests/
│   ├── test_solver.py       Unit test lõi logic (mã hóa vs đánh giá, DPLL vs vét cạn, Agent, Theme)
│   └── test_server.py       Kiểm thử API HTTP (kiểm tra lỗi đầu vào và chống rò rỉ thông tin ẩn)
└── tools/
    ├── build_puzzles.py     Sinh lại bộ câu đố mẫu puzzles/ theo seed cố định
    └── add_portrait.py      Công cụ cắt ảnh chân dung cầu thủ và ghi nguồn vào CREDITS.md
```

**Tách biệt Engine và Agent:** `GameEngine` quản lý toàn bộ đề bài và đáp án ẩn. `LogicAgent` chỉ nhận đối tượng `PlayerView` (`engine.player_view()`) với đúng hai phương thức: `public_state()` (chỉ trả về các manh mối đã mở và kết luận đã chứng minh) và `submit(cell, verdict)`. Trình duyệt web cũng được đối xử tương tự, hoàn toàn không nhận dữ liệu ẩn từ máy chủ.

## Ngôn ngữ manh mối (Clue Language)

- **6 mẫu cốt lõi:** `FACT`, `SAME`, `DIFFERENT`, `EXACTLY`, `AT_LEAST`, `AT_MOST` (các mẫu đếm hỗ trợ `"who": "innocent"` để đếm người vô tội).
- **Các phần mở rộng:**

| Mở rộng | Ví dụ JSON |
|---|---|
| `PARITY` | `{"type":"PARITY","parity":"odd","region":{"kind":"col","index":"A"}}` |
| `COMPARE` | `{"type":"COMPARE","op":"more","left":{"kind":"row","index":1},"right":{"kind":"row","index":2}}` |
| `CONNECTED` | `{"type":"CONNECTED","region":{"kind":"row","index":3},"who":"innocent"}` |
| `IMPLIES` | `{"type":"IMPLIES","if":{"cell":"A1","status":"criminal"},"then":{"cell":"B2","status":"innocent"}}` |
| Vùng nâng cao | `all`, `corners`, `edge`, `ray` (`left`/`right`/`above`/`below`), `between`, `common_neighbors`, `intersect`, `union`, `minus` |

## Định dạng tệp câu đố (JSON)

```json
{
  "id": "my-case",
  "title": "My Case",
  "size": 3,
  "initial": ["B2"],
  "characters": [
    {
      "cell": "A1",
      "name": "Abel",
      "profession": "Cook",
      "status": "criminal",
      "clue": {"type": "EXACTLY", "k": 1, "region": {"kind": "neighbors", "of": "B2"}}
    }
  ]
}
```

- `characters` phải bao phủ toàn bộ ô trên lưới; tên nhân vật phải duy nhất và xếp theo thứ tự bảng chữ cái theo từng hàng (`A1, B1, ..., A2, ...`).
- `status` là đáp án ẩn mà chỉ `GameEngine` được phép đọc.
- `initial` là danh sách các thẻ được mở sẵn lúc bắt đầu. Hệ thống sẽ từ chối tệp nếu có bất kỳ manh mối nào sai trên chính đáp án của nó (trừ khi gắn cờ `allow_false_clues` cho ca thử nghiệm mâu thuẫn).
