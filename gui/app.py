"""
Bộ điều khiển chính của ứng dụng Griductive Solver (Application Controller).
Kết nối tương tác giữa giao diện người dùng (BoardView, SidebarView),
bộ quản lý ván chơi (GameEngine) và tác tử suy luận tự động (LogicAgent).
"""
from __future__ import annotations

import sys
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
        # Đặt tiêu đề ngắn gọn đúng yêu cầu
        self.root.title("Griductive Solver")
        self.root.geometry("1400x880")
        self.root.minsize(1120, 700)
        self.root.configure(bg=Theme.BG_APP)

        # Cài đặt biểu tượng trái bóng thám tử cho cửa sổ
        self._set_app_icon()

        # Khởi tạo tác tử suy luận
        self.agent = LogicAgent()
        # Khởi tạo ván chơi mặc định (3x3)
        default_puzzle = generate_puzzle(seed=3003, rows=3, columns=3)
        self.engine = GameEngine(default_puzzle)

        self.selected_unsolved_cell: str | None = None
        self.is_auto_solving: bool = False

        self._build_layout()
        self._refresh_all(
            feedback_msg="Ván mới sẵn sàng. Mọi manh mối đã mở đều đúng 100% — hãy chứng minh trước khi phán đoán!",
            feedback_type="INFO",
        )

    def _set_app_icon(self) -> None:
        """Cài đặt biểu tượng trái bóng thám tử cho thanh tiêu đề và taskbar."""
        assets_dir = Path(__file__).resolve().parents[1] / "assets"
        icon_ico = assets_dir / "app_icon.ico"
        icon_png = assets_dir / "app_icon.png"

        # 1. Cài đặt qua Tkinter iconbitmap bằng đường dẫn tuyệt đối tới file .ico
        if icon_ico.exists():
            try:
                self.root.iconbitmap(str(icon_ico.resolve()))
            except Exception:
                pass

        # 2. Cài đặt qua Tkinter iconphoto (hỗ trợ hiển thị và tương thích chéo nền tảng)
        if icon_png.exists():
            try:
                self._icon_photo = tk.PhotoImage(file=str(icon_png.resolve()))
                self.root.iconphoto(True, self._icon_photo)
            except Exception:
                pass

        # 3. Kích hoạt trực tiếp qua Win32 API WM_SETICON để đảm bảo 100% hiển thị trên Windows 11
        if sys.platform == "win32" and icon_ico.exists():
            try:
                import ctypes
                self.root.update_idletasks()
                hwnd = self.root.winfo_id()
                parent_hwnd = ctypes.windll.user32.GetParent(hwnd)
                target_hwnd = parent_hwnd if parent_hwnd else hwnd

                WM_SETICON = 0x0080
                ICON_SMALL = 0
                ICON_BIG = 1
                IMAGE_ICON = 1
                LR_LOADFROMFILE = 0x00000010

                ico_full = str(icon_ico.resolve())
                h_sm = ctypes.windll.user32.LoadImageW(0, ico_full, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                h_lg = ctypes.windll.user32.LoadImageW(0, ico_full, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)

                if h_sm:
                    ctypes.windll.user32.SendMessageW(target_hwnd, WM_SETICON, ICON_SMALL, h_sm)
                if h_lg:
                    ctypes.windll.user32.SendMessageW(target_hwnd, WM_SETICON, ICON_BIG, h_lg)
            except Exception:
                pass

    def run(self) -> None:
        """Bắt đầu vòng lặp sự kiện chính của ứng dụng."""
        self.root.mainloop()

    def _build_layout(self) -> None:
        """Xây dựng bố cục chia làm 2 phần: Bàn cờ (trái) và Bảng điều khiển (phải)."""
        container = tk.Frame(self.root, bg=Theme.BG_APP)
        container.pack(fill="both", expand=True)

        # Thanh điều khiển bên phải (Sidebar)
        self.sidebar = SidebarView(
            container,
            on_call_criminal=lambda: self._handle_verdict_call(Status.CRIMINAL),
            on_call_innocent=lambda: self._handle_verdict_call(Status.INNOCENT),
            on_load_puzzle=self._handle_load_puzzle,
            on_new_random=self._handle_new_random,
            on_change_size=self._handle_change_size,
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
            f"Mục tiêu: {cell} ({char_name}). Chọn Criminal hoặc Innocent.",
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
            f"Soi manh mối từ {owner_cell}: Nổi bật {len(refs)} ô cầu thủ liên quan.",
            "INFO",
        )

    def _handle_verdict_call(self, proposed_status: Status) -> None:
        """Xử lý hành động nộp phán đoán: Kiểm tra chứng minh logic từ Knowledge Base."""
        if not self.selected_unsolved_cell:
            self.sidebar.set_feedback("Hãy chọn một ô chưa mở trên bàn cờ trước!", "INFO")
            return

        target_cell = self.selected_unsolved_cell
        res = self.engine.submit(target_cell, proposed_status, self.agent)

        if res is SubmissionResult.ACCEPTED:
            self.selected_unsolved_cell = None
            self.board.set_selection(None)
            self.sidebar.set_selected_card(None, None)
            self._refresh_all(
                f"Chính xác! {target_cell} là {proposed_status.value}.",
                "ACCEPTED",
            )
            if self.engine.is_solved():
                messagebox.showinfo(
                    "Hoàn Thành Vụ Án!",
                    "Chúc mừng! Toàn bộ các cầu thủ đã được xác định hoàn toàn bằng suy luận logic!",
                )

        elif res is SubmissionResult.NOT_PROVABLE:
            self.sidebar.set_feedback(
                f"Từ chối: Chưa đủ dữ kiện để khẳng định {target_cell} là {proposed_status.value}. Không đoán mò!",
                "NOT_PROVABLE",
            )

        elif res is SubmissionResult.CONTRADICTED:
            self.sidebar.set_feedback(
                f"Từ chối: Suy luận logic chứng minh {target_cell} mang trạng thái ngược lại!",
                "CONTRADICTED",
            )

        elif res is SubmissionResult.ALREADY_SOLVED:
            self.sidebar.set_feedback(f"Ô {target_cell} đã được giải trước đó.", "INFO")

        elif res is SubmissionResult.INCONSISTENT:
            self.sidebar.set_feedback("Lỗi: Knowledge Base xảy ra xung đột logic!", "INCONSISTENT")

    def _handle_load_puzzle(self) -> None:
        """Mở hộp thoại cho phép tải câu đố từ file JSON."""
        puzzles_dir = Path(__file__).resolve().parents[1] / "puzzles"
        file_path = filedialog.askopenfilename(
            initialdir=str(puzzles_dir) if puzzles_dir.exists() else ".",
            title="Mở file câu đố",
            filetypes=[("Tệp JSON", "*.json"), ("Tất cả", "*.*")],
        )
        if not file_path:
            return

        try:
            puzzle = load_puzzle_from_json(file_path)
            self.engine = GameEngine(puzzle)
            self.selected_unsolved_cell = None
            self._refresh_all(f"Đã mở file: {puzzle.title}")
        except Exception as e:
            messagebox.showerror("Lỗi Mở File", f"Không thể tải câu đố:\n{e}")

    def _handle_change_size(self, rows: int, cols: int) -> None:
        """Tạo ván chơi mới ngay lập tức với kích thước được chọn (không mở popup dialog)."""
        new_p = generate_puzzle(rows=rows, columns=cols)
        self.engine = GameEngine(new_p)
        self.selected_unsolved_cell = None
        self.board.set_selection(None)
        self.board.set_spotlight(None, set())
        self._refresh_all(f"Đã tạo ván mới {rows}x{cols} (#{new_p.id.split('-')[-1]}).")

    def _handle_new_random(self) -> None:
        """Tạo ván chơi ngẫu nhiên mới với cùng kích thước hiện tại (không mở popup dialog)."""
        r = self.engine.puzzle.rows
        c = self.engine.puzzle.columns
        new_p = generate_puzzle(rows=r, columns=c)
        self.engine = GameEngine(new_p)
        self.selected_unsolved_cell = None
        self.board.set_selection(None)
        self.board.set_spotlight(None, set())
        self._refresh_all(f"Đã tạo ván ngẫu nhiên mới {r}x{c} (#{new_p.id.split('-')[-1]}).")

    def _handle_restart(self) -> None:
        """Đặt lại ván chơi hiện tại về trạng thái 2 thẻ mở ban đầu."""
        self.engine.restart()
        self.selected_unsolved_cell = None
        self._refresh_all("Đã đặt lại ván chơi về ban đầu.")

    def _handle_hint(self) -> None:
        """Hệ thống tìm kiếm và gợi ý một bước đi có thể chứng minh được."""
        if self.engine.is_solved():
            self.sidebar.set_feedback("Vụ án đã được giải quyết xong!", "INFO")
            return

        relevant_clue, deduction = self.agent.get_hint(self.engine.public_state())
        if not deduction:
            self.sidebar.set_feedback("Chưa có ô nào có thể chứng minh bắt buộc tại bước này.", "INFO")
            return

        if relevant_clue:
            refs = set(all_references(relevant_clue))
            self.board.set_spotlight(relevant_clue.owner, refs)

        self.selected_unsolved_cell = deduction.cell
        self.board.set_selection(deduction.cell)

        char_name = next((c.name for c in self.engine.puzzle.characters if c.cell == deduction.cell), "")
        self.sidebar.set_selected_card(deduction.cell, char_name)
        self.sidebar.set_feedback(
            f"Gợi ý: {deduction.cell} ({char_name}) là {deduction.verdict.value}.",
            "HINT",
        )

    def _handle_auto_step(self) -> None:
        """Thực hiện một bước suy luận tự động duy nhất."""
        if self.engine.is_solved():
            self.sidebar.set_feedback("Vụ án đã được giải quyết xong!", "INFO")
            return

        res, deduction = self.engine.auto_step(self.agent)
        if res is SubmissionResult.ACCEPTED and deduction:
            self.selected_unsolved_cell = None
            self.board.set_selection(None)
            self.sidebar.set_selected_card(None, None)
            self._refresh_all(f"Tự động: Đã chứng minh {deduction.cell} là {deduction.verdict.value}.", "ACCEPTED")
            if self.engine.is_solved():
                messagebox.showinfo("Thành Công!", "Đã tự động giải quyết toàn bộ vụ án thành công!")
        else:
            self.sidebar.set_feedback(f"Không thể tự động bước tiếp: {res.value}", "NOT_PROVABLE")

    def _handle_auto_solve(self) -> None:
        """Tự động suy luận giải toàn bộ bàn cờ với hiệu ứng lật thẻ tuần tự."""
        if self.engine.is_solved():
            self.sidebar.set_feedback("Vụ án đã được giải quyết xong!", "INFO")
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
                self._refresh_all(f"Tự động: {ded.cell} = {ded.verdict.value}.", "ACCEPTED")
                self.root.after(200, step)
            else:
                self.is_auto_solving = False
                self.sidebar.btn_solve.configure(state="normal")
                self.sidebar.set_feedback(f"Dừng lại: {res.value}", "NOT_PROVABLE")

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
