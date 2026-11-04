"""
Module xử lý các vùng hình học trên bàn cờ Griductive.
Hỗ trợ tạo các vùng: Hàng (Row), Cột (Column), Hàng xóm 8 hướng (Neighbors),
Danh sách chỉ định (Explicit), Góc (Corners) và Biên (Boundary).
"""
from __future__ import annotations

from typing import Sequence


def coord_to_cell(column_index: int, row_index: int) -> str:
    """Chuyển đổi chỉ số (cột, hàng) sang chuỗi tọa độ (ví dụ: (0, 0) -> 'A1', (1, 2) -> 'B3')."""
    return f"{chr(65 + column_index)}{row_index + 1}"


def cell_to_coord(cell: str) -> tuple[int, int]:
    """Chuyển đổi chuỗi tọa độ 'B2' sang chỉ số (cột, hàng) bắt đầu từ 0 -> (1, 1)."""
    return ord(cell[0].upper()) - 65, int(cell[1:]) - 1


def row_region(row_index: int, total_columns: int) -> tuple[str, ...]:
    """Tập hợp tất cả các ô nằm trên cùng một hàng (row_index tính từ 0)."""
    return tuple(coord_to_cell(col, row_index) for col in range(total_columns))


def column_region(column_index: int, total_rows: int) -> tuple[str, ...]:
    """Tập hợp tất cả các ô nằm trên cùng một cột (column_index tính từ 0)."""
    return tuple(coord_to_cell(column_index, r) for r in range(total_rows))


def neighbors_region(center_cell: str, total_rows: int, total_columns: int) -> tuple[str, ...]:
    """Tập hợp 8 ô lân cận tiếp xúc ngang, dọc hoặc chéo với ô trung tâm (không gồm chính nó)."""
    col, row = cell_to_coord(center_cell)
    result: list[str] = []
    for r in range(max(0, row - 1), min(total_rows, row + 2)):
        for c in range(max(0, col - 1), min(total_columns, col + 2)):
            if (c, r) != (col, row):
                result.append(coord_to_cell(c, r))
    return tuple(result)


def explicit_region(cells: Sequence[str]) -> tuple[str, ...]:
    """Danh sách các ô cụ thể, đảm bảo loại bỏ trùng lặp và không rỗng."""
    deduped = tuple(dict.fromkeys(cells))
    if not deduped:
        raise ValueError("Vùng danh sách ô chỉ định không được để rỗng.")
    return deduped


def corners_region(total_rows: int, total_columns: int) -> tuple[str, ...]:
    """Tập hợp 4 ô góc của bàn cờ."""
    return (
        coord_to_cell(0, 0),
        coord_to_cell(total_columns - 1, 0),
        coord_to_cell(0, total_rows - 1),
        coord_to_cell(total_columns - 1, total_rows - 1),
    )


def boundary_region(total_rows: int, total_columns: int) -> tuple[str, ...]:
    """Tập hợp tất cả các ô nằm trên đường viền ngoài cùng của bàn cờ."""
    cells: list[str] = []
    for r in range(total_rows):
        for c in range(total_columns):
            if r == 0 or r == total_rows - 1 or c == 0 or c == total_columns - 1:
                cells.append(coord_to_cell(c, r))
    return tuple(cells)
