#!/usr/bin/env python3
"""
Điểm khởi chạy chính của ứng dụng trò chơi Griductive Solver.
Khởi tạo và điều hành giao diện người dùng Desktop.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Thêm thư mục Source vào đường dẫn tìm kiếm module của Python
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gui.app import GriductiveApp


def main() -> None:
    # Khởi tạo ứng dụng và chạy vòng lặp sự kiện chính
    app = GriductiveApp()
    app.run()


if __name__ == "__main__":
    main()
