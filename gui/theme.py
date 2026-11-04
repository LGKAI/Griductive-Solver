"""
Định nghĩa hệ thống màu sắc, kiểu chữ và phong cách bóng đá cho Griductive Solver.
Giao diện sân cỏ ban đêm (Stadium Pitch Night), thẻ bài cầu thủ và độ tương phản cao.
"""
from __future__ import annotations


class Theme:
    # ---------------- BẢNG MÀU SÂN CỎ BAN ĐÊM (STADIUM NIGHT) ----------------
    BG_APP = "#0a150f"                  # Nền tổng thể: Đêm sân vận động (Dark Pitch Turf)
    BG_BOARD = "#0d1d15"                # Nền khu vực sân thi đấu
    BG_SIDEBAR = "#12241b"              # Nền thanh điều khiển khu vực kỹ thuật
    BG_SECTION = "#0a1711"              # Nền các khung chức năng (Panel)
    
    # Nền của thẻ cầu thủ
    BG_CARD_FACE_DOWN = "#162b20"       # Thẻ úp mặt bí mật
    BG_CARD_CRIMINAL = "#2a0d11"        # Thẻ Tội phạm (Red Card Thẻ đỏ)
    BG_CARD_INNOCENT = "#0c2d1f"        # Thẻ Vô tội (Fair-play Thẻ xanh)

    # Nền của ô chứa manh mối
    BG_CLUE_FACE_DOWN = "#0e1d16"       # Hộp manh mối khi thẻ đang úp
    BG_CLUE_CRIMINAL = "#1f090c"        # Hộp manh mối Thẻ đỏ
    BG_CLUE_INNOCENT = "#071c14"        # Hộp manh mối Thẻ xanh
    
    # ---------------- BẢNG MÀU VIỀN & HIỆU ỨNG ----------------
    BORDER_DEFAULT = "#223d30"          # Viền thẻ mặc định
    BORDER_SELECTED = "#38bdf8"         # Viền khi chọn thẻ (Đèn sân vận động Sky Blue)
    BORDER_SPOTLIGHT = "#fbbf24"        # Viền chủ manh mối (Vàng quả bóng vàng Ballon d'Or)
    BORDER_HIGHLIGHT = "#34d399"        # Viền các ô liên quan manh mối (Xanh cỏ dạ quang)
    BORDER_CRIMINAL = "#ef4444"         # Viền Thẻ đỏ (Criminal)
    BORDER_INNOCENT = "#10b981"         # Viền Thẻ xanh (Innocent)

    # ---------------- MÀU CHỮ & HUY HIỆU ----------------
    TEXT_LIGHT = "#f8fafc"              # Chữ sáng chính (Trắng sân cỏ)
    TEXT_MUTED = "#8ca396"              # Chữ phụ (Xám xanh)
    TEXT_GOLD = "#fbbf24"               # Điểm nhấn vàng kim
    TEXT_CYAN = "#38bdf8"               # Điểm nhấn xanh neon
    TEXT_PITCH = "#4ade80"              # Xanh lá tươi
    TEXT_CRIMINAL = "#f87171"           # Đỏ thẻ phạt
    TEXT_INNOCENT = "#34d399"           # Xanh lá an toàn

    # ---------------- MÀU NÚT BẤM (BUTTONS) ----------------
    BTN_CRIMINAL_BG = "#dc2626"         # Nút Thẻ đỏ Criminal
    BTN_CRIMINAL_HOVER = "#ef4444"
    BTN_INNOCENT_BG = "#16a34a"         # Nút Fair-play Innocent
    BTN_INNOCENT_HOVER = "#22c55e"
    
    BTN_CTRL_BG = "#1b3527"             # Nút điều khiển thường
    BTN_CTRL_HOVER = "#264a37"
    BTN_PRIMARY_BG = "#0284c7"          # Nút hành động chính (Champions Blue)
    BTN_PRIMARY_HOVER = "#0369a1"

    BTN_SIZE_ACTIVE_BG = "#16a34a"      # Kích thước đang chọn
    BTN_SIZE_INACTIVE_BG = "#16281f"    # Kích thước khác

    # ---------------- KIỂU CHỮ (FONTS) ----------------
    FONT_FAMILY = "Segoe UI"
    FONT_MONO = "Consolas"

    @classmethod
    def font_title(cls) -> tuple[str, int, str]:
        return (cls.FONT_FAMILY, 14, "bold")

    @classmethod
    def font_heading(cls) -> tuple[str, int, str]:
        return (cls.FONT_FAMILY, 11, "bold")

    @classmethod
    def font_bold(cls) -> tuple[str, int, str]:
        return (cls.FONT_FAMILY, 10, "bold")

    @classmethod
    def font_regular(cls) -> tuple[str, int, str]:
        return (cls.FONT_FAMILY, 9, "normal")

    @classmethod
    def font_small(cls) -> tuple[str, int, str]:
        return (cls.FONT_FAMILY, 8, "normal")

    @classmethod
    def font_mono(cls) -> tuple[str, int, str]:
        return (cls.FONT_MONO, 9, "normal")

    @classmethod
    def font_mono_bold(cls) -> tuple[str, int, str]:
        return (cls.FONT_MONO, 9, "bold")
