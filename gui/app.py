"""
Bộ điều khiển chính của ứng dụng Griductive Solver (Application Controller).
Kết nối tương tác giữa giao diện người dùng (BoardView, SidebarView),
bộ quản lý ván chơi (GameEngine) và tác tử suy luận tự động (LogicAgent).
"""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from core.agent import LogicAgent
from core.clues import all_references
from core.cnf import CNFEncoder
from core.engine import GameEngine
from core.models import SolverStats, Status, SubmissionResult
from core.puzzle_generator import generate_puzzle
from core.puzzle_io import load_puzzle_from_json
from gui.board_view import BoardView
from gui.sidebar_view import SidebarView
from gui.theme import Theme


class GriductiveApp:
    """Cửa sổ chính điều phối toàn bộ trò chơi và tác tử logic."""

    def __init__(self, root: tk.Tk | None = None) -> None:
        self.root = root or tk.Tk()
        self.root.title("Griductive Solver — Trò Chơi Suy Luận Logic Mệnh Đề & DPLL SAT")
        self.root.geometry("1440x890")
        self.root.minsize(1160, 720)
        self.root.configure(bg=Theme.BG_APP)

        # Khởi tạo tác tử suy luận diễn dịch
        self.agent = LogicAgent()
        # Khởi tạo ván chơi mặc định (3x3)
        default_puzzle = generate_puzzle(seed=3003, rows=3, columns=3)
        self.engine = GameEngine(default_puzzle)

        self.selected_unsolved_cell: str | None = None
        self.is_auto_solving: bool = False

        self._build_layout()
        self._refresh_all(
            feedback_msg="Ván mới đã sẵn sàng. Mọi manh mối đã mở đều đúng 100% — hãy chứng minh bằng logic trước khi phán đoán!",
            feedback_type="INFO",
        )

    def run(self) -> None:
        """Bắt đầu vòng lặp sự kiện chính của ứng dụng."""
        self.root.mainloop()

    def _build_layout(self) -> None:
        """Xây dựng bố cục tổng thể chia làm 2 phần: Bàn cờ (trái) và Bảng điều khiển (phải)."""
        container = tk.Frame(self.root, bg=Theme.BG_APP)
        container.pack(fill="both", expand=True)

        # Thanh điều khiển bên phải (Sidebar)
        self.sidebar = SidebarView(
            container,
            on_call_criminal=lambda: self._handle_verdict_call(Status.CRIMINAL),
            on_call_innocent=lambda: self._handle_verdict_call(Status.INNOCENT),
            on_load_puzzle=self._handle_load_puzzle,
            on_new_random=self._handle_new_random,
            on_restart=self._handle_restart,
            on_hint=self._handle_hint,
            on_auto_step=self._handle_auto_step,
            on_auto_solve=self._handle_auto_solve,
        )
        self.sidebar.pack(side="right", fill="y")

        # Khu vực bàn cờ bên trái
        board_container = tk.Frame(container, bg=Theme.BG_APP, padx=14, pady=14)
        board_container.pack(side="left", fill="both", expand=True)

        self.board = BoardView(
            board_container,
            on_card_select=self._handle_card_select,
            on_card_spotlight=self._handle_card_spotlight,
        )
        self.board.pack(fill="both", expand=True)

    # ---------------- XỬ LÝ SỰ KIỆN TƯƠNG TÁC NGƯỜI CHƠI ----------------

    def _handle_card_select(self, cell: str) -> None:
        """Người chơi nhấp chuột chọn một thẻ đang úp để chuẩn bị phán đoán."""
        if cell in self.engine._known:
            return
        self.selected_unsolved_cell = cell
        self.board.set_selection(cell)
        self.board.set_spotlight(None, set())

        char_name = next((c.name for c in self.engine.puzzle.characters if c.cell == cell), "")
        self.sidebar.set_selected_card(cell, char_name)
        self.sidebar.set_feedback(
            f"Đã chọn mục tiêu: {cell} ({char_name}). Hãy bấm CRIMINAL hoặc INNOCENT để kết luận.",
            "INFO",
        )

    def _handle_card_spotlight(self, owner_cell: str) -> None:
        """Người chơi nhấp chuột vào một thẻ đã mở để soi rọi manh mối liên quan."""
        clue = self.engine.puzzle.clues.get(owner_cell)
        if not clue:
            return
        refs = set(all_references(clue))
        self.board.set_spotlight(owner_cell, refs)
        self.sidebar.set_feedback(
            f"Chiếu sáng manh mối từ {owner_cell}: Đang làm nổi bật {len(refs)} ô cầu thủ có liên quan.",
            "INFO",
        )

    def _handle_verdict_call(self, proposed_status: Status) -> None:
        """Xử lý hành động nộp phán đoán: Kiểm tra chứng minh logic từ Knowledge Base."""
        if not self.selected_unsolved_cell:
            self.sidebar.set_feedback("Vui lòng nhấp chọn một thẻ chưa giải trên bàn cờ trước!", "INFO")
            return

        target_cell = self.selected_unsolved_cell
        res = self.engine.submit(target_cell, proposed_status, self.agent)

        if res is SubmissionResult.ACCEPTED:
            self.selected_unsolved_cell = None
            self.board.set_selection(None)
            self.sidebar.set_selected_card(None, None)
            self._refresh_all(
                f"CHÍNH XÁC! Logic đã chứng minh thành công: {target_cell} là {proposed_status.value}.",
                "ACCEPTED",
            )
            if self.engine.is_solved():
                messagebox.showinfo(
                    "Hoàn Thành Vụ Án!",
                    "Chúc mừng! Toàn bộ các cầu thủ bí ẩn đã được xác định hoàn toàn bằng suy luận logic, không cần đoán mò!",
                )

        elif res is SubmissionResult.NOT_PROVABLE:
            self.sidebar.set_feedback(
                f"TỪ CHỐI (NOT_PROVABLE): Chưa đủ dữ kiện để bắt buộc {target_cell} là {proposed_status.value}. Không được phỏng đoán!",
                "NOT_PROVABLE",
            )

        elif res is SubmissionResult.CONTRADICTED:
            self.sidebar.set_feedback(
                f"TỪ CHỐI (CONTRADICTED): Suy luận logic chứng minh {target_cell} mang trạng thái NGƯỢC LẠI!",
                "CONTRADICTED",
            )

        elif res is SubmissionResult.ALREADY_SOLVED:
            self.sidebar.set_feedback(f"Ô {target_cell} đã được giải trước đó.", "INFO")

        elif res is SubmissionResult.INCONSISTENT:
            self.sidebar.set_feedback("LỖI XUNG ĐỘT (INCONSISTENT): Knowledge Base không còn mô hình thỏa mãn!", "INCONSISTENT")

    def _handle_load_puzzle(self) -> None:
        """Mở hộp thoại cho phép người chơi tải câu đố từ file JSON."""
        puzzles_dir = Path(__file__).resolve().parents[1] / "puzzles"
        file_path = filedialog.askopenfilename(
            initialdir=str(puzzles_dir) if puzzles_dir.exists() else ".",
            title="Tải Màn Chơi Griductive",
            filetypes=[("Tệp JSON", "*.json"), ("Tất cả các tệp", "*.*")],
        )
        if not file_path:
            return

        try:
            puzzle = load_puzzle_from_json(file_path)
            self.engine = GameEngine(puzzle)
            self.selected_unsolved_cell = None
            self._refresh_all(f"Đã tải thành công câu đố: {puzzle.title}")
        except Exception as e:
            messagebox.showerror("Lỗi Tải File", f"Không thể tải câu đố từ file:\n{e}")

    def _handle_new_random(self) -> None:
        """Mở hộp thoại chọn kích thước và tạo một ván chơi ngẫu nhiên mới."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Tạo Ván Mới")
        dialog.geometry("340x220")
        dialog.configure(bg=Theme.BG_SECTION)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(
            dialog,
            text="Chọn Kích Thước Bàn Cờ:",
            font=Theme.font_heading(),
            fg=Theme.TEXT_GOLD,
            bg=Theme.BG_SECTION,
        ).pack(pady=(16, 10))

        dim_var = tk.StringVar(value="3x3")
        radio_frame = tk.Frame(dialog, bg=Theme.BG_SECTION)
        radio_frame.pack()

        for opt in ("3x3", "3x4", "4x4", "5x5"):
            tk.Radiobutton(
                radio_frame,
                text=f"Lưới {opt}",
                value=opt,
                variable=dim_var,
                font=Theme.font_regular(),
                fg=Theme.TEXT_LIGHT,
                bg=Theme.BG_SECTION,
                selectcolor=Theme.BG_SIDEBAR,
                activebackground=Theme.BG_SECTION,
                activeforeground=Theme.TEXT_LIGHT,
            ).pack(anchor="w", pady=2)

        def on_confirm():
            dim = dim_var.get()
            dialog.destroy()
            r, c = map(int, dim.split("x"))
            new_p = generate_puzzle(rows=r, columns=c)
            self.engine = GameEngine(new_p)
            self.selected_unsolved_cell = None
            self._refresh_all(f"Đã tạo ván chơi mới kích thước {dim} (#{new_p.id.split('-')[-1]})")

        tk.Button(
            dialog,
            text="Bắt Đầu Chơi",
            font=Theme.font_bold(),
            bg=Theme.BTN_PRIMARY_BG,
            fg=Theme.TEXT_LIGHT,
            activebackground=Theme.BTN_PRIMARY_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            relief="flat",
            pady=6,
            command=on_confirm,
        ).pack(pady=14)

    def _handle_restart(self) -> None:
        """Đặt lại ván chơi hiện tại về trạng thái 2 thẻ mở ban đầu."""
        self.engine.restart()
        self.selected_unsolved_cell = None
        self._refresh_all("Đã đặt lại ván chơi về trạng thái ban đầu.")

    def _handle_hint(self) -> None:
        """Hệ thống tìm kiếm và gợi ý một bước đi có thể chứng minh được từ tri thức công khai."""
        if self.engine.is_solved():
            self.sidebar.set_feedback("Vụ án đã được giải quyết hoàn toàn!", "INFO")
            return

        relevant_clue, deduction = self.agent.get_hint(self.engine.public_state())
        if not deduction:
            self.sidebar.set_feedback("Chưa có ô nào có thể chứng minh bắt buộc tại bước này.", "INFO")
            return

        # Chiếu sáng manh mối liên quan nếu tìm thấy
        if relevant_clue:
            refs = set(all_references(relevant_clue))
            self.board.set_spotlight(relevant_clue.owner, refs)

        self.selected_unsolved_cell = deduction.cell
        self.board.set_selection(deduction.cell)

        char_name = next((c.name for c in self.engine.puzzle.characters if c.cell == deduction.cell), "")
        self.sidebar.set_selected_card(deduction.cell, char_name)
        self.sidebar.set_feedback(
            f"GỢI Ý: Ô {deduction.cell} ({char_name}) có thể chứng minh tiếp theo! (Lý do: {deduction.queries[0]})",
            "HINT",
        )

    def _handle_auto_step(self) -> None:
        """Thực hiện một bước suy luận tự động duy nhất."""
        if self.engine.is_solved():
            self.sidebar.set_feedback("Vụ án đã được giải quyết hoàn toàn!", "INFO")
            return

        res, deduction = self.engine.auto_step(self.agent)
        if res is SubmissionResult.ACCEPTED and deduction:
            self.selected_unsolved_cell = None
            self.board.set_selection(None)
            self.sidebar.set_selected_card(None, None)
            self._refresh_all(f"Tự động giải: Đã chứng minh {deduction.cell} là {deduction.verdict.value}.", "ACCEPTED")
            if self.engine.is_solved():
                messagebox.showinfo("Thành Công!", "Đã tự động giải quyết toàn bộ vụ án thành công!")
        else:
            self.sidebar.set_feedback(f"Không thể tự động bước tiếp: {res.value}", "NOT_PROVABLE")

    def _handle_auto_solve(self) -> None:
        """Tự động suy luận giải toàn bộ bàn cờ với hiệu ứng lật thẻ tuần tự."""
        if self.engine.is_solved():
            self.sidebar.set_feedback("Vụ án đã được giải quyết hoàn toàn!", "INFO")
            return

        self.is_auto_solving = True
        self.sidebar.btn_solve.configure(state="disabled")

        def step():
            if not self.is_auto_solving or self.engine.is_solved():
                self.is_auto_solving = False
                self.sidebar.btn_solve.configure(state="normal")
                if self.engine.is_solved():
                    messagebox.showinfo("Hoàn Thành!", "Đã tự động suy luận và mở toàn bộ bàn cờ thành công!")
                return

            res, ded = self.engine.auto_step(self.agent)
            if res is SubmissionResult.ACCEPTED and ded:
                self._refresh_all(f"Tự động giải: Đã chứng minh {ded.cell} là {ded.verdict.value}.", "ACCEPTED")
                # Lặp bước tiếp theo sau 250ms để tạo hiệu ứng thị giác mượt mà
                self.root.after(250, step)
            else:
                self.is_auto_solving = False
                self.sidebar.btn_solve.configure(state="normal")
                self.sidebar.set_feedback(f"Tự động giải dừng lại: {res.value}", "NOT_PROVABLE")

        step()

    # ---------------- ĐỒNG BỘ HÓA GIAO DIỆN ----------------

    def _refresh_all(self, feedback_msg: str = "", feedback_type: str = "INFO") -> None:
        """Đồng bộ hóa toàn bộ trạng thái hiển thị của bàn cờ và bảng điều khiển."""
        state = self.engine.public_state()
        name_lookup = {char.cell: char.name for char in state.characters}

        # Dựng lại lưới nếu kích thước hoặc ID ván chơi thay đổi
        if (
            len(self.board.card_frames) != self.engine.puzzle.cell_count
            or getattr(self, "_current_puzzle_id", None) != self.engine.puzzle.id
        ):
            self._current_puzzle_id = self.engine.puzzle.id
            self.board.build_grid(self.engine.puzzle.rows, self.engine.puzzle.columns, self.engine.puzzle.characters)

        # Cập nhật hiển thị từng thẻ bài
        self.board.update_state(state, name_lookup)

        # Cập nhật thông tin ván chơi trên sidebar
        self.sidebar.set_puzzle_info(
            title=self.engine.puzzle.title,
            rows=self.engine.puzzle.rows,
            cols=self.engine.puzzle.columns,
            solved=len(state.known_verdicts),
            total=self.engine.puzzle.cell_count,
        )

        # Cập nhật thông số thống kê CNF và solver
        encoder = CNFEncoder(state.characters)
        encoded_kb = encoder.encode_public(state)
        total_stats = SolverStats()
        for entry in self.engine.trace:
            total_stats = total_stats.plus(entry.stats)

        self.sidebar.update_metrics(
            primary_vars=encoded_kb.primary_variables,
            aux_vars=encoded_kb.auxiliary_variables,
            clauses=encoded_kb.clause_count,
            stats=total_stats,
        )

        # Cập nhật danh sách nhật ký suy luận
        self.sidebar.update_trace(self.engine.trace)

        if feedback_msg:
            self.sidebar.set_feedback(feedback_msg, feedback_type)
