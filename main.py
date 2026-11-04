#!/usr/bin/env python3
"""
Griductive Solver - Điểm khởi chạy chính của ứng dụng.
Bật độ phân giải cao High-DPI và khởi tạo giao diện trò chơi.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Thêm thư mục Source vào đường dẫn tìm kiếm module của Python
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Kích hoạt DPI awareness trên Windows để giao diện đạt độ nét tối đa, không bị mờ
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor High DPI v2
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # System High DPI
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

from gui.app import GriductiveApp


def main() -> None:
    app = GriductiveApp()
    app.run()


if __name__ == "__main__":
    main()
