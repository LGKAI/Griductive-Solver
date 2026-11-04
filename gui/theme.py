"""
Định nghĩa hệ thống màu sắc, kiểu chữ và phong cách hiển thị giao diện.
Sử dụng phong cách Dark Slate sang trọng, hiện đại và độ tương phản cao.
"""
from __future__ import annotations


class Theme:
    # ---------------- BẢNG MÀU NỀN ----------------
    BG_APP = "#0f172a"                  # Nền tổng thể cửa sổ chính (Slate Dark Navy)
    BG_BOARD = "#0f172a"                # Nền khu vực bàn cờ
    BG_SIDEBAR = "#1e293b"              # Nền thanh công cụ điều khiển bên phải
    BG_SECTION = "#0f172a"              # Nền các khung chức năng con trong sidebar
    
    # Nền của thẻ nhân vật theo trạng thái
    BG_CARD_FACE_DOWN = "#1e293b"       # Thẻ úp mặt bí mật
    BG_CARD_CRIMINAL = "#2e0f14"        # Thẻ mở mặt: Tội phạm (Criminal - Đỏ thẫm sang trọng)
    BG_CARD_INNOCENT = "#092e20"        # Thẻ mở mặt: Vô tội (Innocent - Xanh ngọc lục bảo)

    # Nền của hộp chứa nội dung manh mối bên trong thẻ
    BG_CLUE_FACE_DOWN = "#131c2e"       # Hộp manh mối khi thẻ đang úp
    BG_CLUE_CRIMINAL = "#1f090b"        # Hộp manh mối khi là Criminal
    BG_CLUE_INNOCENT = "#051f15"        # Hộp manh mối khi là Innocent
    
    # ---------------- BẢNG MÀU VIỀN ----------------
    BORDER_DEFAULT = "#334155"          # Viền thẻ mặc định
    BORDER_SELECTED = "#38bdf8"         # Viền khi người chơi chọn thẻ để phán đoán (Xanh Sky phát sáng)
    BORDER_SPOTLIGHT = "#fbbf24"        # Viền chủ sở hữu manh mối đang xem (Vàng kim hổ phách)
    BORDER_HIGHLIGHT = "#06b6d4"        # Viền các ô mục tiêu liên quan đến manh mối (Cyan neon)
    BORDER_CRIMINAL = "#ef4444"         # Viền thẻ Criminal đã mở
    BORDER_INNOCENT = "#10b981"         # Viền thẻ Innocent đã mở

    # ---------------- MÀU CHỮ & HUY HIỆU ----------------
    TEXT_LIGHT = "#f8fafc"              # Chữ sáng chính (Trắng ngà)
    TEXT_MUTED = "#94a3b8"              # Chữ phụ mờ (Xám bạc)
    TEXT_GOLD = "#fbbf24"               # Chữ điểm nhấn vàng kim
    TEXT_CYAN = "#38bdf8"               # Chữ điểm nhấn xanh neon
    TEXT_CRIMINAL = "#f87171"           # Chữ cảnh báo tội phạm
    TEXT_INNOCENT = "#34d399"           # Chữ thông báo vô tội

    # ---------------- MÀU NÚT BẤM (BUTTONS) ----------------
    BTN_CRIMINAL_BG = "#dc2626"         # Nút gọi CRIMINAL
    BTN_CRIMINAL_HOVER = "#ef4444"
    BTN_INNOCENT_BG = "#059669"         # Nút gọi INNOCENT
    BTN_INNOCENT_HOVER = "#10b981"
    
    BTN_CTRL_BG = "#334155"             # Nút điều khiển thông thường
    BTN_CTRL_HOVER = "#475569"
    BTN_PRIMARY_BG = "#4f46e5"          # Nút hành động chính (Auto Solve - Indigo)
    BTN_PRIMARY_HOVER = "#6366f1"

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
        return (cls.FONT_MONO, 8, "normal")

    @classmethod
    def font_mono_bold(cls) -> tuple[str, int, str]:
        return (cls.FONT_MONO, 9, "bold")
