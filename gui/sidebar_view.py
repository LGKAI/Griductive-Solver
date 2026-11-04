"""
Thanh điều khiển bên phải (Sidebar) của trò chơi Griductive Solver.
Bao gồm: Bảng nộp phán đoán, điều khiển ván chơi (chọn kích thước trực tiếp không popup),
thống kê số liệu giải thuật DPLL và nhật ký suy luận.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Sequence

from core.models import SolverStats, TraceEntry
from gui.theme import Theme


class SidebarView(tk.Frame):
    """Bảng điều khiển trung tâm với giao diện sân cỏ tinh gọn, nút bấm tối giản."""

    def __init__(
        self,
        master: tk.Widget,
        on_call_criminal: Callable[[], None],
        on_call_innocent: Callable[[], None],
        on_load_puzzle: Callable[[], None],
        on_new_random: Callable[[], None],
        on_change_size: Callable[[int, int], None],
        on_restart: Callable[[], None],
        on_hint: Callable[[], None],
        on_auto_step: Callable[[], None],
        on_auto_solve: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(master, bg=Theme.BG_SIDEBAR, width=380, padx=14, pady=12, **kwargs)
        self.pack_propagate(False)

        self.on_call_criminal = on_call_criminal
        self.on_call_innocent = on_call_innocent
        self.on_load_puzzle = on_load_puzzle
        self.on_new_random = on_new_random
        self.on_change_size = on_change_size
        self.on_restart = on_restart
        self.on_hint = on_hint
        self.on_auto_step = on_auto_step
        self.on_auto_solve = on_auto_solve

        self.size_buttons: dict[str, tk.Button] = {}
        self.current_dim = "3x3"

        self._build_ui()

    def _build_ui(self) -> None:
        # Tiêu đề ứng dụng
        self.title_lbl = tk.Label(
            self,
            text="⚽ GRIDUCTIVE SOLVER",
            font=Theme.font_title(),
            fg=Theme.TEXT_PITCH,
            bg=Theme.BG_SIDEBAR,
            anchor="w",
        )
        self.title_lbl.pack(fill="x")

        self.info_lbl = tk.Label(
            self,
            text="Ván: 3x3 | Tiến độ: 0/9",
            font=Theme.font_regular(),
            fg=Theme.TEXT_MUTED,
            bg=Theme.BG_SIDEBAR,
            anchor="w",
        )
        self.info_lbl.pack(fill="x", pady=(2, 10))

        # ---------------- KHUNG PHÁN ĐOÁN (VERDICT) ----------------
        verdict_box = tk.LabelFrame(
            self,
            text=" 🎯 Phán đoán ",
            font=Theme.font_heading(),
            fg=Theme.TEXT_GOLD,
            bg=Theme.BG_SECTION,
            padx=10,
            pady=8,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_DEFAULT,
        )
        verdict_box.pack(fill="x", pady=(0, 10))

        self.target_lbl = tk.Label(
            verdict_box,
            text="Mục tiêu: Chưa chọn ô",
            font=Theme.font_bold(),
            fg=Theme.TEXT_MUTED,
            bg=Theme.BG_SECTION,
            anchor="w",
        )
        self.target_lbl.pack(fill="x", pady=(0, 8))

        btn_row = tk.Frame(verdict_box, bg=Theme.BG_SECTION)
        btn_row.pack(fill="x")

        # Nút phán đoán Criminal (Thẻ đỏ)
        self.btn_crm = tk.Button(
            btn_row,
            text="Criminal",
            font=Theme.font_bold(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BTN_CRIMINAL_BG,
            activebackground=Theme.BTN_CRIMINAL_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=7,
            command=self.on_call_criminal,
        )
        self.btn_crm.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # Nút phán đoán Innocent (Thẻ xanh)
        self.btn_inn = tk.Button(
            btn_row,
            text="Innocent",
            font=Theme.font_bold(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BTN_INNOCENT_BG,
            activebackground=Theme.BTN_INNOCENT_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=7,
            command=self.on_call_innocent,
        )
        self.btn_inn.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # Dòng thông báo trạng thái
        self.feedback_lbl = tk.Label(
            verdict_box,
            text="Nhấp chuột vào một ô trên sân để phán đoán.",
            font=Theme.font_small(),
            fg=Theme.TEXT_MUTED,
            bg=Theme.BG_SECTION,
            wraplength=330,
            justify="left",
            pady=6,
        )
        self.feedback_lbl.pack(fill="x")

        # ---------------- KHUNG ĐIỀU KHIỂN (CONTROLS) ----------------
        ctrl_box = tk.LabelFrame(
            self,
            text=" ⚙️ Điều khiển ",
            font=Theme.font_heading(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BG_SECTION,
            padx=10,
            pady=8,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_DEFAULT,
        )
        ctrl_box.pack(fill="x", pady=(0, 10))

        # Chọn kích thước trực tiếp (không mở popup)
        size_lbl = tk.Label(
            ctrl_box,
            text="Kích thước sân:",
            font=Theme.font_small(),
            fg=Theme.TEXT_MUTED,
            bg=Theme.BG_SECTION,
            anchor="w",
        )
        size_lbl.pack(fill="x", pady=(0, 3))

        size_frame = tk.Frame(ctrl_box, bg=Theme.BG_SECTION)
        size_frame.pack(fill="x", pady=(0, 8))

        sizes = [("3x3", 3, 3), ("3x4", 3, 4), ("4x4", 4, 4), ("5x5", 5, 5)]
        for label, r, c in sizes:
            btn = tk.Button(
                size_frame,
                text=label,
                font=Theme.font_mono_bold(),
                fg=Theme.TEXT_LIGHT,
                bg=Theme.BTN_SIZE_ACTIVE_BG if label == "3x3" else Theme.BTN_CTRL_BG,
                activebackground=Theme.BTN_CTRL_HOVER,
                activeforeground=Theme.TEXT_LIGHT,
                cursor="hand2",
                relief="flat",
                pady=4,
                command=lambda rows=r, cols=c, lbl=label: self._on_size_click(rows, cols, lbl),
            )
            btn.pack(side="left", fill="x", expand=True, padx=2)
            self.size_buttons[label] = btn

        # Hàng nút 1: Tải file & Ván mới
        row1 = tk.Frame(ctrl_box, bg=Theme.BG_SECTION)
        row1.pack(fill="x", pady=(0, 4))

        self.btn_load = tk.Button(
            row1,
            text="Mở file",
            font=Theme.font_regular(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BTN_CTRL_BG,
            activebackground=Theme.BTN_CTRL_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=5,
            command=self.on_load_puzzle,
        )
        self.btn_load.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_new = tk.Button(
            row1,
            text="Ván mới",
            font=Theme.font_regular(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BTN_CTRL_BG,
            activebackground=Theme.BTN_CTRL_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=5,
            command=self.on_new_random,
        )
        self.btn_new.pack(side="right", fill="x", expand=True, padx=(3, 0))

        # Hàng nút 2: Chơi lại & Gợi ý
        row2 = tk.Frame(ctrl_box, bg=Theme.BG_SECTION)
        row2.pack(fill="x", pady=(0, 4))

        self.btn_restart = tk.Button(
            row2,
            text="Chơi lại",
            font=Theme.font_regular(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BTN_CTRL_BG,
            activebackground=Theme.BTN_CTRL_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=5,
            command=self.on_restart,
        )
        self.btn_restart.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_hint = tk.Button(
            row2,
            text="Gợi ý",
            font=Theme.font_bold(),
            fg=Theme.TEXT_GOLD,
            bg=Theme.BTN_CTRL_BG,
            activebackground=Theme.BTN_CTRL_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=5,
            command=self.on_hint,
        )
        self.btn_hint.pack(side="right", fill="x", expand=True, padx=(3, 0))

        # Hàng nút 3: Đi 1 bước & Tự động giải
        row3 = tk.Frame(ctrl_box, bg=Theme.BG_SECTION)
        row3.pack(fill="x")

        self.btn_step = tk.Button(
            row3,
            text="Đi 1 bước",
            font=Theme.font_regular(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BTN_CTRL_BG,
            activebackground=Theme.BTN_CTRL_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=6,
            command=self.on_auto_step,
        )
        self.btn_step.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_solve = tk.Button(
            row3,
            text="Tự động giải",
            font=Theme.font_bold(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BTN_PRIMARY_BG,
            activebackground=Theme.BTN_PRIMARY_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=6,
            command=self.on_auto_solve,
        )
        self.btn_solve.pack(side="right", fill="x", expand=True, padx=(3, 0))

        # ---------------- KHUNG SỐ LIỆU DPLL (METRICS) ----------------
        metrics_box = tk.LabelFrame(
            self,
            text=" 📊 Thống kê DPLL ",
            font=Theme.font_heading(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BG_SECTION,
            padx=10,
            pady=6,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_DEFAULT,
        )
        metrics_box.pack(fill="x", pady=(0, 10))

        self.metric_vars_lbl = tk.Label(
            metrics_box,
            text="Biến: 0 (0 phụ)",
            font=Theme.font_mono(),
            fg=Theme.TEXT_CYAN,
            bg=Theme.BG_SECTION,
            anchor="w",
        )
        self.metric_vars_lbl.pack(fill="x")

        self.metric_clauses_lbl = tk.Label(
            metrics_box,
            text="Mệnh đề CNF: 0",
            font=Theme.font_mono(),
            fg=Theme.TEXT_CYAN,
            bg=Theme.BG_SECTION,
            anchor="w",
        )
        self.metric_clauses_lbl.pack(fill="x")

        self.metric_solver_lbl = tk.Label(
            metrics_box,
            text="Gọi SAT: 0 | Quyết định: 0",
            font=Theme.font_mono(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BG_SECTION,
            anchor="w",
        )
        self.metric_solver_lbl.pack(fill="x")

        self.metric_detail_lbl = tk.Label(
            metrics_box,
            text="Lan truyền: 0 | 0.0 ms",
            font=Theme.font_mono(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BG_SECTION,
            anchor="w",
        )
        self.metric_detail_lbl.pack(fill="x")

        # ---------------- KHUNG NHẬT KÝ SUY LUẬN (TRACE) ----------------
        trace_box = tk.LabelFrame(
            self,
            text=" 📝 Nhật ký suy luận ",
            font=Theme.font_heading(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BG_SECTION,
            padx=6,
            pady=6,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_DEFAULT,
        )
        trace_box.pack(fill="both", expand=True)

        list_container = tk.Frame(trace_box, bg=Theme.BG_SECTION)
        list_container.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_container, orient="vertical")
        self.trace_list = tk.Listbox(
            list_container,
            yscrollcommand=scrollbar.set,
            font=Theme.font_mono(),
            bg="#07120c",
            fg=Theme.TEXT_LIGHT,
            selectbackground=Theme.BORDER_SELECTED,
            selectforeground=Theme.TEXT_LIGHT,
            relief="flat",
            highlightthickness=0,
        )
        scrollbar.configure(command=self.trace_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.trace_list.pack(side="left", fill="both", expand=True)

    def _on_size_click(self, rows: int, cols: int, label: str) -> None:
        """Xử lý khi người dùng bấm chọn kích thước sân mới (không cần popup)."""
        self.set_active_size(rows, cols)
        self.on_change_size(rows, cols)

    def set_active_size(self, rows: int, cols: int) -> None:
        """Cập nhật nút kích thước đang hoạt động."""
        dim_key = f"{rows}x{cols}"
        self.current_dim = dim_key
        for key, btn in self.size_buttons.items():
            if key == dim_key:
                btn.configure(bg=Theme.BTN_SIZE_ACTIVE_BG, fg=Theme.TEXT_LIGHT)
            else:
                btn.configure(bg=Theme.BTN_CTRL_BG, fg=Theme.TEXT_LIGHT)

    def set_selected_card(self, cell: str | None, char_name: str | None = None) -> None:
        """Cập nhật thông tin thẻ đang chọn để phán đoán."""
        if cell:
            name_text = f" ({char_name})" if char_name else ""
            self.target_lbl.configure(text=f"Mục tiêu: {cell}{name_text}", fg=Theme.TEXT_PITCH)
            self.btn_crm.configure(state="normal")
            self.btn_inn.configure(state="normal")
        else:
            self.target_lbl.configure(text="Mục tiêu: Chưa chọn ô", fg=Theme.TEXT_MUTED)
            self.btn_crm.configure(state="normal")
            self.btn_inn.configure(state="normal")

    def set_puzzle_info(self, title: str, rows: int, cols: int, solved: int, total: int) -> None:
        """Cập nhật thông tin tiêu đề và tiến độ."""
        self.set_active_size(rows, cols)
        self.info_lbl.configure(
            text=f"Sân: {rows}x{cols} | Tiến độ: {solved}/{total} cầu thủ"
        )

    def set_feedback(self, message: str, msg_type: str = "INFO") -> None:
        """Hiển thị thông báo phản hồi kết quả suy luận ngắn gọn, rõ ràng."""
        color_map = {
            "INFO": Theme.TEXT_MUTED,
            "ACCEPTED": Theme.TEXT_PITCH,
            "NOT_PROVABLE": Theme.TEXT_GOLD,
            "CONTRADICTED": Theme.TEXT_CRIMINAL,
            "INCONSISTENT": Theme.TEXT_CRIMINAL,
            "HINT": Theme.TEXT_CYAN,
        }
        color = color_map.get(msg_type, Theme.TEXT_MUTED)
        self.feedback_lbl.configure(text=message, fg=color)

    def update_metrics(self, primary_vars: int, aux_vars: int, clauses: int, stats: SolverStats) -> None:
        """Cập nhật các số liệu thống kê solver."""
        self.metric_vars_lbl.configure(text=f"Biến: {primary_vars} ({aux_vars} phụ)")
        self.metric_clauses_lbl.configure(text=f"Mệnh đề: {clauses} CNF")
        self.metric_solver_lbl.configure(
            text=f"Gọi SAT: {stats.sat_calls} | Quyết định: {stats.decisions}"
        )
        self.metric_detail_lbl.configure(
            text=f"Lan truyền: {stats.propagations} | {stats.runtime_ms:.1f} ms"
        )

    def update_trace(self, trace: Sequence[TraceEntry]) -> None:
        """Cập nhật danh sách nhật ký các bước suy luận."""
        self.trace_list.delete(0, tk.END)
        for i, entry in enumerate(trace, 1):
            symbol = "🟥" if entry.verdict.value == "CRIMINAL" else "🟩"
            time_str = f"{entry.stats.runtime_ms:.1f}ms"
            display_text = f"#{i} {symbol} {entry.cell} = {entry.verdict.value} ({time_str})"
            self.trace_list.insert(tk.END, display_text)
        if trace:
            self.trace_list.see(tk.END)
