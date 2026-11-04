"""
Bộ mã hóa logic mệnh đề sang dạng chuẩn hội CNF (Conjunctive Normal Form).
Tự động chuyển đổi các manh mối mức cao thành các mệnh đề CNF logic mệnh đề.
Quy ước biểu diễn:
- Literal dương (x > 0): Nhân vật tại ô đó là CRIMINAL (True).
- Literal âm (x < 0): Nhân vật tại ô đó là INNOCENT (False).
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Iterable, Mapping

from .clues import evaluate_clue, validate_clue
from .models import Character, Clue, ClueKind, PublicState, Status

Clause = tuple[int, ...]


@dataclass(frozen=True)
class EncodedKB:
    """Cơ sở tri thức đã mã hóa dạng CNF kèm thông tin số lượng biến và mệnh đề."""
    clauses: tuple[Clause, ...]
    variable_map: Mapping[str, int]        # Ánh xạ tọa độ ô -> Chỉ số biến chính (1..N)
    primary_variables: int                 # Số lượng biến chính (bằng số ô bàn cờ)
    auxiliary_variables: int               # Số lượng biến phụ sinh ra trong quá trình mã hóa

    @property
    def total_variables(self) -> int:
        return self.primary_variables + self.auxiliary_variables

    @property
    def clause_count(self) -> int:
        return len(self.clauses)


class CNFEncoder:
    """Bộ mã hóa CNF có khả năng tái sử dụng.
    Đảm bảo ánh xạ biến chính có tính xác định theo thứ tự bảng chữ cái tên nhân vật."""

    def __init__(self, characters: Iterable[Character]):
        # Sắp xếp nhân vật theo thứ tự bảng chữ cái không phân biệt hoa thường
        ordered = sorted(characters, key=lambda item: (item.name.casefold(), item.cell))
        self.variable_map: dict[str, int] = {
            char.cell: index + 1 for index, char in enumerate(ordered)
        }
        self.reverse_map: dict[int, str] = {
            var: cell for cell, var in self.variable_map.items()
        }
        self.valid_cells: set[str] = set(self.variable_map.keys())
        self.primary_variables: int = len(self.variable_map)
        self._next_aux_var: int = self.primary_variables + 1

    def _allocate_aux_var(self) -> int:
        """Cấp phát một biến phụ mới bắt đầu từ N + 1."""
        var = self._next_aux_var
        self._next_aux_var += 1
        return var

    def literal(self, cell: str, status: Status) -> int:
        """Chuyển đổi trạng thái của một ô thành literal nguyên: dương nếu Criminal, âm nếu Innocent."""
        var = self.variable_map[cell]
        return var if status is Status.CRIMINAL else -var

    def encode_public(self, state: PublicState) -> EncodedKB:
        """Mã hóa toàn bộ trạng thái công khai (manh mối đã mở + phán đoán đã chứng minh) sang CNF."""
        self._next_aux_var = self.primary_variables + 1
        clauses: list[Clause] = []

        # 1. Mã hóa tất cả các manh mối đã được lật mở
        for clue in state.revealed_clues:
            clauses.extend(self.encode_clue(clue))

        # 2. Thêm mệnh đề đơn vị (unit clauses) cho các ô đã được chứng minh trạng thái
        for cell, status in state.known_verdicts.items():
            clauses.append((self.literal(cell, status),))

        aux_count = self._next_aux_var - (self.primary_variables + 1)
        return EncodedKB(
            clauses=tuple(clauses),
            variable_map=dict(self.variable_map),
            primary_variables=self.primary_variables,
            auxiliary_variables=aux_count,
        )

    def encode_clue(self, clue: Clue) -> list[Clause]:
        """Chuyển đổi một manh mối có cấu trúc thành danh sách các mệnh đề CNF tương đương."""
        validate_clue(clue, self.valid_cells)
        lit = self.literal

        # 1. Manh mối FACT: Một người có trạng thái xác định -> Unit clause
        if clue.kind is ClueKind.FACT:
            return [(lit(clue.targets[0], clue.status),)]

        # 2. Manh mối SAME: (Ci <-> Cj) <=> (~Ci v Cj) ^ (Ci v ~Cj)
        if clue.kind is ClueKind.SAME:
            a, b = (self.variable_map[c] for c in clue.targets)
            return [(-a, b), (a, -b)]

        # 3. Manh mối DIFFERENT: (Ci XOR Cj) <=> (Ci v Cj) ^ (~Ci v ~Cj)
        if clue.kind is ClueKind.DIFFERENT:
            a, b = (self.variable_map[c] for c in clue.targets)
            return [(a, b), (-a, -b)]

        # 4. Manh mối EXACTLY: Kết hợp AT_LEAST k và AT_MOST k
        if clue.kind is ClueKind.EXACTLY:
            return self._encode_at_least(clue.region, clue.k) + self._encode_at_most(clue.region, clue.k)

        # 5. Manh mối AT_LEAST
        if clue.kind is ClueKind.AT_LEAST:
            return self._encode_at_least(clue.region, clue.k)

        # 6. Manh mối AT_MOST
        if clue.kind is ClueKind.AT_MOST:
            return self._encode_at_most(clue.region, clue.k)

        # 7. Phần mở rộng PARITY
        if clue.kind is ClueKind.PARITY:
            return self._encode_parity(clue.region, clue.parity)

        # 8. Phần mở rộng COUNT_COMPARE
        if clue.kind is ClueKind.COUNT_COMPARE:
            return self._encode_count_compare(clue)

        raise NotImplementedError(f"Loại manh mối chưa được hỗ trợ mã hóa: {clue.kind}")

    def _encode_at_most(self, region: tuple[str, ...], k: int) -> list[Clause]:
        """Mã hóa ràng buộc: Có nhiều nhất k biến trong vùng nhận giá trị True.
        Nguyên lý tổ hợp: Trong mọi tập con gồm (k + 1) biến, ít nhất một biến phải nhận giá trị False."""
        if k >= len(region):
            return []
        if k < 0:
            return [()]  # Mệnh đề rỗng biểu thị xung đột không thể thỏa mãn
        return [
            tuple(-self.variable_map[cell] for cell in combo)
            for combo in combinations(region, k + 1)
        ]

    def _encode_at_least(self, region: tuple[str, ...], k: int) -> list[Clause]:
        """Mã hóa ràng buộc: Có ít nhất k biến trong vùng nhận giá trị True.
        Tương đương: Có nhiều nhất (|vùng| - k) biến nhận giá trị False.
        Nguyên lý tổ hợp: Trong mọi tập con gồm (|vùng| - k + 1) biến, ít nhất một biến phải là True."""
        if k <= 0:
            return []
        if k > len(region):
            return [()]  # Xung đột không thể thỏa mãn
        subset_size = len(region) - k + 1
        return [
            tuple(self.variable_map[cell] for cell in combo)
            for combo in combinations(region, subset_size)
        ]

    def _encode_parity(self, region: tuple[str, ...], parity: str) -> list[Clause]:
        """Mã hóa ràng buộc tính chẵn lẻ (EVEN / ODD) trên một vùng.
        - Với vùng nhỏ (<= 3 ô): Cấm trực tiếp các tổ hợp có parity sai.
        - Với vùng lớn: Sử dụng chuỗi biến phụ XOR (Tseitin transformation) để tạo biến phụ auxiliary."""
        if not region:
            if parity == "EVEN":
                return []
            return [()]

        vars_list = [self.variable_map[c] for c in region]

        if len(vars_list) <= 3:
            clauses: list[Clause] = []
            for combo in product((False, True), repeat=len(vars_list)):
                count = sum(combo)
                is_even = (count % 2 == 0)
                wanted_even = (parity == "EVEN")
                if is_even != wanted_even:
                    clause = tuple(-v if val else v for v, val in zip(vars_list, combo))
                    clauses.append(clause)
            return clauses

        # Chuỗi biến phụ Tseitin cho XOR:
        # t_1 <=> x_1 XOR x_2
        # t_2 <=> t_1 XOR x_3 ...
        clauses: list[Clause] = []
        cur = vars_list[0]
        for next_var in vars_list[1:]:
            t = self._allocate_aux_var()
            clauses.append((-t, cur, next_var))
            clauses.append((-t, -cur, -next_var))
            clauses.append((t, -cur, next_var))
            clauses.append((t, cur, -next_var))
            cur = t

        if parity == "ODD":
            clauses.append((cur,))
        else:
            clauses.append((-cur,))
        return clauses

    def _encode_count_compare(self, clue: Clue) -> list[Clause]:
        """Mã hóa manh mối so sánh số lượng COUNT_COMPARE giữa 2 vùng."""
        refs = tuple(dict.fromkeys(clue.region + clue.region_b))
        if len(refs) > 12:
            raise ValueError(f"Manh mối COUNT_COMPARE {clue.id} tham chiếu vượt quá giới hạn 12 ô.")
        clauses: list[Clause] = []
        for combo in product((False, True), repeat=len(refs)):
            assignment = {cell: Status.from_boolean(val) for cell, val in zip(refs, combo)}
            if not evaluate_clue(clue, assignment):
                clause = tuple(-self.variable_map[c] if val else self.variable_map[c] for c, val in zip(refs, combo))
                clauses.append(clause)
        return clauses
