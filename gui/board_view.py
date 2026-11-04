"""
Thành phần hiển thị bàn cờ suy luận dạng lưới Griductive.
Quản lý các thẻ nhân vật, hiển thị chân dung cầu thủ sắc nét và hiệu ứng thị giác.
"""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from typing import Callable, Mapping

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from core.clues import all_references, describe_clue
from core.models import Character, Clue, PublicState, Status
from gui.theme import Theme


class BoardView(tk.Frame):
    """Khu vực bàn cờ chứa lưới các thẻ nhân vật, tọa độ hàng/cột và hiệu ứng viền."""

    def __init__(
        self,
        master: tk.Widget,
        on_card_select: Callable[[str], None],
        on_card_spotlight: Callable[[str], None],
        **kwargs,
    ) -> None:
        super().__init__(master, bg=Theme.BG_BOARD, **kwargs)
        self.on_card_select = on_card_select
        self.on_card_spotlight = on_card_spotlight

        # Bộ nhớ lưu trữ ảnh chân dung cầu thủ
        self.portrait_images: list[object] = []
        self._load_portraits()

        self.card_frames: dict[str, tk.Frame] = {}
        self.card_widgets: dict[str, dict[str, tk.Widget]] = {}

        self.selected_cell: str | None = None
        self.spotlight_owner: str | None = None
        self.highlighted_cells: set[str] = set()

    def _load_portraits(self) -> None:
        """Tải và cắt 25 chân dung cầu thủ từ ảnh gốc với chất lượng cao chống nhòe."""
        asset_path = Path(__file__).resolve().parents[1] / "assets" / "suspect_portraits.png"
        if not asset_path.exists():
            return

        target_size = (76, 76)  # Kích thước chuẩn sắc nét cho ảnh đại diện

        if HAS_PIL:
            # Sử dụng Pillow với thuật toán LANCZOS để hình ảnh đạt độ sắc nét tối đa
            try:
                full_image = Image.open(str(asset_path)).convert("RGBA")
                tile_w = full_image.width / 5.0
                tile_h = full_image.height / 5.0

                for idx in range(25):
                    col = idx % 5
                    row = idx // 5
                    crop_box = (
                        int(col * tile_w),
                        int(row * tile_h),
                        int((col + 1) * tile_w),
                        int((row + 1) * tile_h),
                    )
                    cropped = full_image.crop(crop_box)
                    resized = cropped.resize(target_size, Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(resized)
                    self.portrait_images.append(photo)
                return
            except Exception:
                self.portrait_images.clear()

        # Fallback bằng Tkinter PhotoImage thuần nếu môi trường không có Pillow
        try:
            full_img = tk.PhotoImage(file=str(asset_path))
            tile_w = full_img.width() // 5
            tile_h = full_img.height() // 5
            for idx in range(25):
                col, row = idx % 5, idx // 5
                tile = tk.PhotoImage(width=tile_w, height=tile_h)
                tile.tk.call(
                    tile, "copy", full_img,
                    "-from", col * tile_w, row * tile_h, (col + 1) * tile_w, (row + 1) * tile_h,
                    "-to", 0, 0
                )
                self.portrait_images.append(tile.subsample(3, 3))
        except Exception:
            self.portrait_images = []

    def build_grid(self, rows: int, columns: int, characters: tuple[Character, ...]) -> None:
        """Khởi dựng lưới các ô thẻ bài kèm tiêu đề tọa độ hàng và cột."""
        # Xóa các thành phần giao diện cũ
        for widget in self.winfo_children():
            widget.destroy()
        self.card_frames.clear()
        self.card_widgets.clear()
        self.selected_cell = None
        self.spotlight_owner = None
        self.highlighted_cells.clear()

        # Thiết lập trọng số co giãn cho các hàng và cột
        for c in range(columns + 1):
            self.grid_columnconfigure(c, weight=1 if c > 0 else 0)
        for r in range(rows + 1):
            self.grid_rowconfigure(r, weight=1 if r > 0 else 0)

        # Vẽ tiêu đề cột (A, B, C...)
        for c in range(columns):
            col_letter = chr(65 + c)
            lbl = tk.Label(
                self,
                text=f"Cột {col_letter}",
                font=Theme.font_heading(),
                fg=Theme.TEXT_CYAN,
                bg=Theme.BG_BOARD,
                pady=4,
            )
            lbl.grid(row=0, column=c + 1, sticky="nsew")

        # Vẽ tiêu đề hàng (1, 2, 3...)
        for r in range(rows):
            lbl = tk.Label(
                self,
                text=f"Hàng {r + 1}",
                font=Theme.font_heading(),
                fg=Theme.TEXT_CYAN,
                bg=Theme.BG_BOARD,
                padx=6,
            )
            lbl.grid(row=r + 1, column=0, sticky="nsew")

        # Khởi tạo các thẻ bài nhân vật
        char_by_cell = {char.cell: char for char in characters}
        for r in range(rows):
            for c in range(columns):
                cell_coord = f"{chr(65 + c)}{r + 1}"
                char = char_by_cell.get(cell_coord)
                if not char:
                    continue

                card_frame = tk.Frame(
                    self,
                    bg=Theme.BG_CARD_FACE_DOWN,
                    highlightthickness=2,
                    highlightbackground=Theme.BORDER_DEFAULT,
                    padx=8,
                    pady=8,
                    cursor="hand2",
                )
                card_frame.grid(row=r + 1, column=c + 1, padx=6, pady=6, sticky="nsew")
                card_frame.bind("<Button-1>", lambda e, cell=cell_coord: self._on_card_click(cell))

                # Hàng tiêu đề thẻ: Tọa độ ô + Huy hiệu trạng thái
                header_frame = tk.Frame(card_frame, bg=Theme.BG_CARD_FACE_DOWN)
                header_frame.pack(fill="x", side="top")
                header_frame.bind("<Button-1>", lambda e, cell=cell_coord: self._on_card_click(cell))

                coord_lbl = tk.Label(
                    header_frame,
                    text=f"📍 {cell_coord}",
                    font=Theme.font_mono_bold(),
                    fg=Theme.TEXT_GOLD,
                    bg=Theme.BG_CARD_FACE_DOWN,
                )
                coord_lbl.pack(side="left")
                coord_lbl.bind("<Button-1>", lambda e, cell=cell_coord: self._on_card_click(cell))

                status_badge = tk.Label(
                    header_frame,
                    text="🔒 ÚP MẶT",
                    font=Theme.font_small(),
                    fg=Theme.TEXT_MUTED,
                    bg="#2d3748",
                    padx=6,
                    pady=2,
                )
                status_badge.pack(side="right")
                status_badge.bind("<Button-1>", lambda e, cell=cell_coord: self._on_card_click(cell))

                # Khu vực hồ sơ cầu thủ: Ảnh chân dung + Tên + Vị trí
                profile_frame = tk.Frame(card_frame, bg=Theme.BG_CARD_FACE_DOWN)
                profile_frame.pack(fill="x", pady=(6, 8), side="top")
                profile_frame.bind("<Button-1>", lambda e, cell=cell_coord: self._on_card_click(cell))

                portrait_img = self.portrait_images[char.portrait_index] if char.portrait_index < len(self.portrait_images) else None
                portrait_lbl = tk.Label(
                    profile_frame,
                    image=portrait_img if portrait_img else "",
                    text="" if portrait_img else "⚽",
                    font=("Segoe UI", 24) if not portrait_img else Theme.font_regular(),
                    bg=Theme.BG_CARD_FACE_DOWN,
                    highlightthickness=1,
                    highlightbackground=Theme.BORDER_DEFAULT,
                )
                portrait_lbl.pack(side="left", padx=(0, 8))
                portrait_lbl.bind("<Button-1>", lambda e, cell=cell_coord: self._on_card_click(cell))

                info_frame = tk.Frame(profile_frame, bg=Theme.BG_CARD_FACE_DOWN)
                info_frame.pack(side="left", fill="both", expand=True)
                info_frame.bind("<Button-1>", lambda e, cell=cell_coord: self._on_card_click(cell))

                name_lbl = tk.Label(
                    info_frame,
                    text=char.name,
                    font=Theme.font_bold(),
                    fg=Theme.TEXT_LIGHT,
                    bg=Theme.BG_CARD_FACE_DOWN,
                    anchor="w",
                )
                name_lbl.pack(fill="x")
                name_lbl.bind("<Button-1>", lambda e, cell=cell_coord: self._on_card_click(cell))

                prof_lbl = tk.Label(
                    info_frame,
                    text=char.profession,
                    font=Theme.font_small(),
                    fg=Theme.TEXT_MUTED,
                    bg=Theme.BG_CARD_FACE_DOWN,
                    anchor="w",
                )
                prof_lbl.pack(fill="x")
                prof_lbl.bind("<Button-1>", lambda e, cell=cell_coord: self._on_card_click(cell))

                # Khung hiển thị nội dung manh mối logic
                clue_frame = tk.Frame(
                    card_frame,
                    bg=Theme.BG_CLUE_FACE_DOWN,
                    highlightthickness=1,
                    highlightbackground="#2d3748",
                    padx=6,
                    pady=6,
                )
                clue_frame.pack(fill="both", expand=True, side="bottom")
                clue_frame.bind("<Button-1>", lambda e, cell=cell_coord: self._on_card_click(cell))

                clue_lbl = tk.Label(
                    clue_frame,
                    text="🔒 MANH MỐI BÍ MẬT\n(Phán đoán đúng để lật thẻ)",
                    font=Theme.font_small(),
                    fg=Theme.TEXT_MUTED,
                    bg=Theme.BG_CLUE_FACE_DOWN,
                    wraplength=180,
                    justify="left",
                    anchor="nw",
                )
                clue_lbl.pack(fill="both", expand=True)
                clue_lbl.bind("<Button-1>", lambda e, cell=cell_coord: self._on_card_click(cell))

                self.card_frames[cell_coord] = card_frame
                self.card_widgets[cell_coord] = {
                    "header_frame": header_frame,
                    "status_badge": status_badge,
                    "profile_frame": profile_frame,
                    "portrait_lbl": portrait_lbl,
                    "info_frame": info_frame,
                    "name_lbl": name_lbl,
                    "prof_lbl": prof_lbl,
                    "clue_frame": clue_frame,
                    "clue_lbl": clue_lbl,
                }

    def update_state(self, state: PublicState, name_lookup: Mapping[str, str]) -> None:
        """Cập nhật giao diện thẻ bài dựa theo trạng thái công khai PublicState hiện tại."""
        revealed_map = {clue.owner: clue for clue in state.revealed_clues}

        for cell, frame in self.card_frames.items():
            widgets = self.card_widgets[cell]
            status_badge = widgets["status_badge"]
            clue_frame = widgets["clue_frame"]
            clue_lbl = widgets["clue_lbl"]
            name_lbl = widgets["name_lbl"]
            prof_lbl = widgets["prof_lbl"]
            header_frame = widgets["header_frame"]
            profile_frame = widgets["profile_frame"]
            portrait_lbl = widgets["portrait_lbl"]
            info_frame = widgets["info_frame"]

            is_revealed = cell in state.known_verdicts
            known_status = state.known_verdicts.get(cell)

            if is_revealed and known_status:
                clue = revealed_map.get(cell)
                clue_desc = describe_clue(clue, name_lookup) if clue else "Không có manh mối bổ sung."

                if known_status is Status.CRIMINAL:
                    card_bg = Theme.BG_CARD_CRIMINAL
                    clue_bg = Theme.BG_CLUE_CRIMINAL
                    border_color = Theme.BORDER_CRIMINAL
                    badge_bg = Theme.BTN_CRIMINAL_BG
                    badge_text = "🚨 CRIMINAL"
                    clue_text_color = "#fef08a"  # Vàng sáng nổi bật trên nền tối
                else:
                    card_bg = Theme.BG_CARD_INNOCENT
                    clue_bg = Theme.BG_CLUE_INNOCENT
                    border_color = Theme.BORDER_INNOCENT
                    badge_bg = Theme.BTN_INNOCENT_BG
                    badge_text = "🛡️ INNOCENT"
                    clue_text_color = "#a7f3d0"  # Xanh ngọc sáng nổi bật

                # Cập nhật màu nền cho toàn bộ các panel bên trong thẻ
                frame.configure(bg=card_bg, highlightbackground=border_color)
                header_frame.configure(bg=card_bg)
                profile_frame.configure(bg=card_bg)
                info_frame.configure(bg=card_bg)
                name_lbl.configure(bg=card_bg, fg=Theme.TEXT_LIGHT)
                prof_lbl.configure(bg=card_bg, fg=Theme.TEXT_MUTED)
                portrait_lbl.configure(bg=card_bg, highlightbackground=border_color)

                status_badge.configure(text=badge_text, bg=badge_bg, fg=Theme.TEXT_LIGHT, font=Theme.font_bold())
                clue_frame.configure(bg=clue_bg, highlightbackground=border_color)
                clue_lbl.configure(
                    text=f"📜 {clue_desc}",
                    fg=clue_text_color,
                    bg=clue_bg,
                    font=Theme.font_regular(),
                )
            else:
                # Trạng thái thẻ đang úp
                card_bg = Theme.BG_CARD_FACE_DOWN
                clue_bg = Theme.BG_CLUE_FACE_DOWN

                frame.configure(bg=card_bg, highlightbackground=Theme.BORDER_DEFAULT)
                header_frame.configure(bg=card_bg)
                profile_frame.configure(bg=card_bg)
                info_frame.configure(bg=card_bg)
                name_lbl.configure(bg=card_bg, fg=Theme.TEXT_LIGHT)
                prof_lbl.configure(bg=card_bg, fg=Theme.TEXT_MUTED)
                portrait_lbl.configure(bg=card_bg, highlightbackground=Theme.BORDER_DEFAULT)

                status_badge.configure(
                    text="🔒 ÚP MẶT",
                    bg="#334155",
                    fg=Theme.TEXT_MUTED,
                    font=Theme.font_small(),
                )
                clue_frame.configure(bg=clue_bg, highlightbackground="#2d3748")
                clue_lbl.configure(
                    text="🔒 MANH MỐI BÍ MẬT\n(Nhấp chọn & phán đoán để mở)",
                    fg=Theme.TEXT_MUTED,
                    bg=clue_bg,
                    font=Theme.font_small(),
                )

        self._refresh_borders()

    def set_selection(self, cell: str | None) -> None:
        """Đánh dấu thẻ chưa giải đang được người chơi chọn để đưa ra phán đoán."""
        self.selected_cell = cell
        self._refresh_borders()

    def set_spotlight(self, owner_cell: str | None, referenced_cells: set[str]) -> None:
        """Kích hoạt hiệu ứng chiếu sáng manh mối: viền vàng cho thẻ chủ, viền xanh cho mục tiêu."""
        self.spotlight_owner = owner_cell
        self.highlighted_cells = set(referenced_cells)
        self._refresh_borders()

    def _refresh_borders(self) -> None:
        """Vẽ lại màu sắc và độ dày viền của từng thẻ bài."""
        for cell, frame in self.card_frames.items():
            if cell == self.selected_cell:
                # Đang được chọn để phán đoán -> Viền xanh Sky phát sáng
                frame.configure(highlightbackground=Theme.BORDER_SELECTED, highlightthickness=3)
            elif cell == self.spotlight_owner:
                # Là thẻ chủ của manh mối đang xem -> Viền vàng kim
                frame.configure(highlightbackground=Theme.BORDER_SPOTLIGHT, highlightthickness=3)
            elif cell in self.highlighted_cells:
                # Là ô nằm trong vùng manh mối đang xem -> Viền xanh cyan
                frame.configure(highlightbackground=Theme.BORDER_HIGHLIGHT, highlightthickness=3)
            else:
                # Thẻ bình thường -> Giữ viền theo trạng thái đã mở hoặc mặc định
                status = self.card_widgets[cell]["status_badge"].cget("text")
                if "CRIMINAL" in status:
                    frame.configure(highlightbackground=Theme.BORDER_CRIMINAL, highlightthickness=2)
                elif "INNOCENT" in status:
                    frame.configure(highlightbackground=Theme.BORDER_INNOCENT, highlightthickness=2)
                else:
                    frame.configure(highlightbackground=Theme.BORDER_DEFAULT, highlightthickness=2)

    def _on_card_click(self, cell: str) -> None:
        """Xử lý nhấp chuột: thẻ mở thì xem manh mối, thẻ úp thì chọn để phán đoán."""
        widgets = self.card_widgets.get(cell)
        if not widgets:
            return
        status_text = widgets["status_badge"].cget("text")
        if "CRIMINAL" in status_text or "INNOCENT" in status_text:
            # Thẻ đã mở: Kích hoạt soi rọi manh mối
            self.on_card_spotlight(cell)
        else:
            # Thẻ chưa mở: Chọn thẻ để phán đoán
            self.on_card_select(cell)
