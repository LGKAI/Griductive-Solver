"""
Thanh điều khiển bên phải (Sidebar) của trò chơi Griductive Solver.
Bao gồm: Bảng nộp phán đoán, các nút điều khiển ván chơi, bảng theo dõi số liệu SAT và nhật ký suy luận.
"""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Sequence

from core.models import SolverStats, TraceEntry
from gui.theme import Theme


class SidebarView(tk.Frame):
    """Bảng điều khiển trung tâm quản lý thao tác người chơi và thống kê thuật toán."""

    def __init__(
        self,
        master: tk.Widget,
        on_call_criminal: Callable[[], None],
        on_call_innocent: Callable[[], None],
        on_load_puzzle: Callable[[], None],
        on_new_random: Callable[[], None],
        on_restart: Callable[[], None],
        on_hint: Callable[[], None],
        on_auto_step: Callable[[], None],
        on_auto_solve: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(master, bg=Theme.BG_SIDEBAR, width=390, padx=14, pady=12, **kwargs)
        self.pack_propagate(False)

        self.on_call_criminal = on_call_criminal
        self.on_call_innocent = on_call_innocent
        self.on_load_puzzle = on_load_puzzle
        self.on_new_random = on_new_random
        self.on_restart = on_restart
        self.on_hint = on_hint
        self.on_auto_step = on_auto_step
        self.on_auto_solve = on_auto_solve

        self._build_ui()

    def _build_ui(self) -> None:
        # Tiêu đề ứng dụng
        self.title_lbl = tk.Label(
            self,
            text="⚡ GRIDUCTIVE SOLVER",
            font=Theme.font_title(),
            fg=Theme.TEXT_CYAN,
            bg=Theme.BG_SIDEBAR,
            anchor="w",
        )
        self.title_lbl.pack(fill="x")

        self.info_lbl = tk.Label(
            self,
            text="Đang nạp dữ liệu câu đố...",
            font=Theme.font_regular(),
            fg=Theme.TEXT_MUTED,
            bg=Theme.BG_SIDEBAR,
            anchor="w",
        )
        self.info_lbl.pack(fill="x", pady=(2, 10))

        # ---------------- KHUNG NỘP PHÁN ĐOÁN (VERDICT SUBMISSION) ----------------
        verdict_box = tk.LabelFrame(
            self,
            text=" 🎯 Phán Đoán Logic (Không Đoán Mò) ",
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
            text="Thẻ đang chọn: (Chưa chọn ô)",
            font=Theme.font_bold(),
            fg=Theme.TEXT_MUTED,
            bg=Theme.BG_SECTION,
            anchor="w",
        )
        self.target_lbl.pack(fill="x", pady=(0, 8))

        btn_row = tk.Frame(verdict_box, bg=Theme.BG_SECTION)
        btn_row.pack(fill="x")

        # Nút phán đoán Tội phạm (CRIMINAL)
        self.btn_crm = tk.Button(
            btn_row,
            text="🚨 CRIMINAL",
            font=Theme.font_bold(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BTN_CRIMINAL_BG,
            activebackground=Theme.BTN_CRIMINAL_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=8,
            command=self.on_call_criminal,
        )
        self.btn_crm.pack(side="left", fill="x", expand=True, padx=(0, 4))

        # Nút phán đoán Vô tội (INNOCENT)
        self.btn_inn = tk.Button(
            btn_row,
            text="🛡️ INNOCENT",
            font=Theme.font_bold(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BTN_INNOCENT_BG,
            activebackground=Theme.BTN_INNOCENT_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=8,
            command=self.on_call_innocent,
        )
        self.btn_inn.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # Dòng thông báo trạng thái phán đoán
        self.feedback_lbl = tk.Label(
            verdict_box,
            text="Nhấp chuột vào một ô thẻ đang úp để bắt đầu suy luận.",
            font=Theme.font_small(),
            fg=Theme.TEXT_MUTED,
            bg=Theme.BG_SECTION,
            wraplength=340,
            justify="left",
            pady=6,
        )
        self.feedback_lbl.pack(fill="x")

        # ---------------- KHUNG ĐIỀU KHIỂN (CONTROLS) ----------------
        ctrl_box = tk.LabelFrame(
            self,
            text=" ⚙️ Điều Khiển Trò Chơi ",
            font=Theme.font_heading(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BG_SECTION,
            padx=10,
            pady=8,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_DEFAULT,
        )
        ctrl_box.pack(fill="x", pady=(0, 10))

        # Hàng nút 1: Tải file & Sinh ván mới
        row1 = tk.Frame(ctrl_box, bg=Theme.BG_SECTION)
        row1.pack(fill="x", pady=(0, 4))

        self.btn_load = tk.Button(
            row1,
            text="📂 Tải Màn (Load)",
            font=Theme.font_regular(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BTN_CTRL_BG,
            activebackground=Theme.BTN_CTRL_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=4,
            command=self.on_load_puzzle,
        )
        self.btn_load.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_new = tk.Button(
            row1,
            text="🎲 Màn Ngẫu Nhiên",
            font=Theme.font_regular(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BTN_CTRL_BG,
            activebackground=Theme.BTN_CTRL_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=4,
            command=self.on_new_random,
        )
        self.btn_new.pack(side="right", fill="x", expand=True, padx=(3, 0))

        # Hàng nút 2: Chơi lại & Gợi ý bước đi
        row2 = tk.Frame(ctrl_box, bg=Theme.BG_SECTION)
        row2.pack(fill="x", pady=(0, 4))

        self.btn_restart = tk.Button(
            row2,
            text="🔄 Bắt Đầu Lại",
            font=Theme.font_regular(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BTN_CTRL_BG,
            activebackground=Theme.BTN_CTRL_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=4,
            command=self.on_restart,
        )
        self.btn_restart.pack(side="left", fill="x", expand=True, padx=(0, 3))

        self.btn_hint = tk.Button(
            row2,
            text="💡 Gợi Ý (Hint)",
            font=Theme.font_regular(),
            fg=Theme.TEXT_GOLD,
            bg=Theme.BTN_CTRL_BG,
            activebackground=Theme.BTN_CTRL_HOVER,
            activeforeground=Theme.TEXT_LIGHT,
            cursor="hand2",
            relief="flat",
            pady=4,
            command=self.on_hint,
        )
        self.btn_hint.pack(side="right", fill="x", expand=True, padx=(3, 0))

        # Hàng nút 3: Đi 1 bước & Tự động giải
        row3 = tk.Frame(ctrl_box, bg=Theme.BG_SECTION)
        row3.pack(fill="x")

        self.btn_step = tk.Button(
            row3,
            text="⚡ Đi 1 Bước",
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
            text="🚀 Tự Động Giải (Auto)",
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

        # ---------------- KHUNG SỐ LIỆU DPLL (METRICS DASHBOARD) ----------------
        metrics_box = tk.LabelFrame(
            self,
            text=" 📊 Thống Kê Giải Thuật DPLL SAT ",
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
            text="Biến: 0 Chính | 0 Phụ",
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
            text="Lần gọi SAT: 0 | Quyết định: 0",
            font=Theme.font_mono(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BG_SECTION,
            anchor="w",
        )
        self.metric_solver_lbl.pack(fill="x")

        self.metric_detail_lbl = tk.Label(
            metrics_box,
            text="Lan truyền: 0 | Quay lui: 0 | Thời gian: 0.0 ms",
            font=Theme.font_mono(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BG_SECTION,
            anchor="w",
        )
        self.metric_detail_lbl.pack(fill="x")

        # ---------------- KHUNG NHẬT KÝ SUY LUẬN (TRACE LOG) ----------------
        trace_box = tk.LabelFrame(
            self,
            text=" 📝 Nhật Ký Suy Luận Từng Bước ",
            font=Theme.font_heading(),
            fg=Theme.TEXT_LIGHT,
            bg=Theme.BG_SECTION,
            padx=6,
            pady=6,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_DEFAULT,
        )
        trace_box.pack(fill="both", expand=True)

        self.trace_list = tk.Listbox(
            trace_box,
            font=Theme.font_mono(),
            bg="#090d16",
            fg="#7dd3fc",
            selectbackground="#1e293b",
            selectforeground="#ffffff",
            relief="flat",
            highlightthickness=0,
        )
        scrollbar = tk.Scrollbar(trace_box, orient="vertical", command=self.trace_list.yview)
        self.trace_list.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.trace_list.pack(side="left", fill="both", expand=True)

    def set_puzzle_info(self, title: str, rows: int, cols: int, solved: int, total: int) -> None:
        """Cập nhật thông tin tiêu đề câu đố và tiến độ giải."""
        self.title_lbl.configure(text=f"⚡ {title.upper()}")
        percent = int(solved / total * 100) if total > 0 else 0
        self.info_lbl.configure(
            text=f"Kích thước: {rows}×{cols} | Tiến độ: {solved}/{total} ({percent}%)",
            fg=Theme.TEXT_CYAN if solved == total else Theme.TEXT_MUTED,
        )

    def set_selected_card(self, cell: str | None, name: str | None) -> None:
        """Hiển thị mục tiêu cầu thủ đang được người chơi chọn."""
        if cell and name:
            self.target_lbl.configure(text=f"Mục tiêu: {cell} ({name})", fg=Theme.TEXT_GOLD)
        else:
            self.target_lbl.configure(text="Thẻ đang chọn: (Chưa chọn ô)", fg=Theme.TEXT_MUTED)

    def set_feedback(self, text: str, status_type: str = "INFO") -> None:
        """Cập nhật thông điệp phản hồi kết quả phán đoán."""
        color_map = {
            "ACCEPTED": "#34d399",     # Xanh ngọc thành công
            "NOT_PROVABLE": "#fb923c", # Cam cảnh báo chưa chứng minh được
            "CONTRADICTED": "#f87171", # Đỏ mâu thuẫn
            "INCONSISTENT": "#ef4444", # Đỏ đậm xung đột KB
            "INFO": Theme.TEXT_MUTED,
            "HINT": Theme.TEXT_GOLD,   # Vàng gợi ý
        }
        self.feedback_lbl.configure(text=text, fg=color_map.get(status_type, Theme.TEXT_LIGHT))

    def update_metrics(
        self,
        primary_vars: int,
        aux_vars: int,
        clauses: int,
        stats: SolverStats,
    ) -> None:
        """Cập nhật các số liệu thống kê của mô hình CNF và bộ giải SAT."""
        self.metric_vars_lbl.configure(text=f"Biến: {primary_vars} Chính | {aux_vars} Phụ")
        self.metric_clauses_lbl.configure(text=f"Mệnh đề CNF: {clauses}")
        self.metric_solver_lbl.configure(text=f"Lần gọi SAT: {stats.sat_calls} | Quyết định: {stats.decisions}")
        self.metric_detail_lbl.configure(
            text=f"Lan truyền: {stats.propagations} | Quay lui: {stats.backtracks} | Thời gian: {stats.runtime_ms:.1f} ms"
        )

    def update_trace(self, trace: Sequence[TraceEntry]) -> None:
        """Ghi nhận danh sách các bước suy luận đã được chứng minh vào nhật ký."""
        self.trace_list.delete(0, tk.END)
        for entry in trace:
            line = f"Bước {entry.step:02d}: {entry.cell} là {entry.verdict.value} => Mở {entry.revealed_clue_id}"
            self.trace_list.insert(tk.END, line)
        if trace:
            self.trace_list.see(tk.END)
