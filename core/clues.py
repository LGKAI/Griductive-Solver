"""
Module định nghĩa ngữ nghĩa, kiểm tra tính hợp lệ và đánh giá manh mối.
Bao gồm:
- Hàm trích xuất ô liên quan (all_references) phục vụ chiếu sáng manh mối trên giao diện.
- Kiểm tra hợp lệ (validate_clue).
- Bộ đánh giá trực tiếp ngữ nghĩa (evaluate_clue - Direct Semantic Evaluator).
- Tạo câu mô tả tự nhiên tiếng Việt (describe_clue).
"""
from __future__ import annotations

from typing import Mapping
from .models import Clue, ClueKind, Status


def all_references(clue: Clue) -> tuple[str, ...]:
    """Trả về toàn bộ các ô tọa độ được nhắc đến hoặc đếm trong manh mối này."""
    seen: dict[str, None] = {}
    for cell in clue.targets:
        seen[cell] = None
    for cell in clue.region:
        seen[cell] = None
    for cell in clue.region_b:
        seen[cell] = None
    return tuple(seen.keys())


def validate_clue(clue: Clue, valid_cells: set[str]) -> None:
    """Kiểm tra tính hợp lệ của tham số manh mối so với kích thước và quy tắc bàn cờ."""
    refs = all_references(clue)
    for cell in refs:
        if cell not in valid_cells:
            raise ValueError(f"Manh mối {clue.id} tham chiếu ô không hợp lệ '{cell}' nằm ngoài bàn cờ.")

    if clue.kind is ClueKind.FACT:
        if len(clue.targets) != 1 or clue.status is None:
            raise ValueError(f"Manh mối FACT {clue.id} yêu cầu đúng 1 mục tiêu và 1 trạng thái xác định.")

    elif clue.kind in (ClueKind.SAME, ClueKind.DIFFERENT):
        if len(clue.targets) != 2:
            raise ValueError(f"Manh mối {clue.kind.value} {clue.id} yêu cầu đúng 2 mục tiêu.")
        if clue.targets[0] == clue.targets[1]:
            raise ValueError(f"Manh mối {clue.kind.value} {clue.id} yêu cầu 2 mục tiêu phân biệt nhau.")

    elif clue.kind in (ClueKind.EXACTLY, ClueKind.AT_LEAST, ClueKind.AT_MOST):
        if not clue.region:
            raise ValueError(f"Manh mối đếm {clue.id} yêu cầu vùng không được rỗng.")
        if clue.k is None or not (0 <= clue.k <= len(clue.region)):
            raise ValueError(
                f"Manh mối đếm {clue.id} yêu cầu 0 <= k <= |vùng| (k={clue.k}, |vùng|={len(clue.region)})."
            )

    elif clue.kind is ClueKind.PARITY:
        if not clue.region:
            raise ValueError(f"Manh mối PARITY {clue.id} yêu cầu vùng không được rỗng.")
        if clue.parity not in ("EVEN", "ODD"):
            raise ValueError(f"Manh mối PARITY {clue.id} yêu cầu tính chẵn lẻ phải là 'EVEN' hoặc 'ODD'.")

    elif clue.kind is ClueKind.COUNT_COMPARE:
        if not clue.region or not clue.region_b:
            raise ValueError(f"Manh mối COUNT_COMPARE {clue.id} yêu cầu cả 2 vùng region và region_b.")
        if clue.comparison not in ("EQ", "GT", "LT"):
            raise ValueError(f"Manh mối COUNT_COMPARE {clue.id} so sánh phải là 'EQ', 'GT' hoặc 'LT'.")


def evaluate_clue(clue: Clue, assignment: Mapping[str, Status]) -> bool:
    """Bộ đánh giá trực tiếp ngữ nghĩa (Direct Semantic Evaluator).
    Kiểm tra xem manh mối có thỏa mãn với một phép gán hoàn chỉnh hay không
    mà không cần gọi bộ mã hóa CNF."""
    def count_criminals(region: tuple[str, ...]) -> int:
        return sum(1 for c in region if assignment[c] is Status.CRIMINAL)

    if clue.kind is ClueKind.FACT:
        return assignment[clue.targets[0]] is clue.status

    if clue.kind is ClueKind.SAME:
        return assignment[clue.targets[0]] is assignment[clue.targets[1]]

    if clue.kind is ClueKind.DIFFERENT:
        return assignment[clue.targets[0]] is not assignment[clue.targets[1]]

    count = count_criminals(clue.region)

    if clue.kind is ClueKind.EXACTLY:
        return count == clue.k

    if clue.kind is ClueKind.AT_LEAST:
        return count >= clue.k

    if clue.kind is ClueKind.AT_MOST:
        return count <= clue.k

    if clue.kind is ClueKind.PARITY:
        is_even = (count % 2 == 0)
        return is_even if clue.parity == "EVEN" else not is_even

    if clue.kind is ClueKind.COUNT_COMPARE:
        count_b = count_criminals(clue.region_b)
        if clue.comparison == "EQ":
            return count == count_b
        if clue.comparison == "GT":
            return count > count_b
        if clue.comparison == "LT":
            return count < count_b

    raise NotImplementedError(f"Loại manh mối chưa được hỗ trợ: {clue.kind}")


def describe_clue(clue: Clue, name_lookup: Mapping[str, str] | None = None) -> str:
    """Tạo câu văn mô tả manh mối tự nhiên bằng tiếng Việt để hiển thị trên thẻ bài."""
    def get_name(cell: str) -> str:
        if name_lookup and cell in name_lookup:
            return f"{name_lookup[cell]} ({cell})"
        return cell

    def format_cells(cells: tuple[str, ...]) -> str:
        if not cells:
            return "rỗng"
        if len(cells) <= 3:
            return ", ".join(get_name(c) for c in cells)
        return f"{len(cells)} ô [{', '.join(get_name(c) for c in cells[:2])}, ...]"

    if clue.kind is ClueKind.FACT:
        st_text = "TỘI PHẠM (CRIMINAL)" if clue.status is Status.CRIMINAL else "VÔ TỘI (INNOCENT)"
        return f"{get_name(clue.targets[0])} chắc chắn là {st_text}."

    if clue.kind is ClueKind.SAME:
        return f"{get_name(clue.targets[0])} và {get_name(clue.targets[1])} CÙNG trạng thái."

    if clue.kind is ClueKind.DIFFERENT:
        return f"{get_name(clue.targets[0])} và {get_name(clue.targets[1])} KHÁC trạng thái."

    if clue.kind is ClueKind.EXACTLY:
        return f"Có ĐÚNG {clue.k} Criminal trong số: {format_cells(clue.region)}."

    if clue.kind is ClueKind.AT_LEAST:
        return f"Có ÍT NHẤT {clue.k} Criminal trong số: {format_cells(clue.region)}."

    if clue.kind is ClueKind.AT_MOST:
        return f"Có NHIỀU NHẤT {clue.k} Criminal trong số: {format_cells(clue.region)}."

    if clue.kind is ClueKind.PARITY:
        parity_text = "CHẴN" if clue.parity == "EVEN" else "LẺ"
        return f"Số Criminal trong ({format_cells(clue.region)}) là số {parity_text}."

    if clue.kind is ClueKind.COUNT_COMPARE:
        comp_text = {"EQ": "bằng", "GT": "nhiều hơn", "LT": "ít hơn"}.get(clue.comparison, clue.comparison)
        return f"Số Criminal ở ({format_cells(clue.region)}) {comp_text} số Criminal ở ({format_cells(clue.region_b)})."

    return f"Manh mối {clue.id} ({clue.kind.value})"
