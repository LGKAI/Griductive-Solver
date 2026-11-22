"""Bộ mã hóa tự động các manh mối sang dạng chuẩn hội CNF.

Biến logic được đánh số nguyên dương theo chuẩn DIMACS; literal là ``+v`` hoặc ``-v``.
Biến chính ``C_i`` (True = criminal) được đánh số theo chỉ số row-major cộng 1 nên ánh xạ
hoàn toàn tất định. Các biến phụ do bộ mã hóa sinh ra luôn đánh số sau toàn bộ biến chính.

Ràng buộc đếm hỗ trợ hai chế độ mã hóa:

* ``direct``  - Mã hóa tổ hợp trực tiếp, không dùng biến phụ:
    ``AT_MOST k``  trên ``x_1..x_n``: mọi tập con kích thước ``(k+1)`` đều không thể cùng True.
    ``AT_LEAST k`` trên ``x_1..x_n``: mọi tập con kích thước ``(n-k+1)`` phải có ít nhất 1 True.
* ``counter`` - Bộ đếm tuần tự (unary counter) với cổng Tseitin:
    ``s[i][j] <-> (có ít nhất j literal đúng trong x_1..x_i)`` với
    ``s[i][j] = s[i-1][j] OR (x_i AND s[i-1][j-1])``.

Chế độ ``auto`` (mặc định) dùng ``direct`` khi số mệnh đề không vượt quá 300 và tự chuyển
sang ``counter`` khi vùng lớn để tránh bùng nổ tổ hợp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import comb
from typing import Iterable, Sequence, Union

from .board import Board
from .clues import CRIMINAL, Clue

Lit = int
# Term có thể là một literal nguyên hoặc hằng bool Python True / False (được rút gọn tại chỗ)
Term = Union[int, bool]

CARDINALITY_MODES = ("auto", "direct", "counter")
DIRECT_CLAUSE_LIMIT = 300    # Ngưỡng chuyển sang bộ đếm tuần tự ở chế độ 'auto'
DIRECT_HARD_LIMIT = 200_000  # Giới hạn an toàn bộ nhớ ngay cả khi ép chế độ 'direct'


class VarMap:
    """Ánh xạ tất định hai chiều giữa tọa độ ô trên lưới và chỉ số biến chính (1..N^2)."""

    def __init__(self, board: Board):
        self.board = board
        self._var = {cell: i + 1 for i, cell in enumerate(board.cells)}
        self._cell = {v: c for c, v in self._var.items()}

    @property
    def num_primary(self) -> int:
        return len(self._var)

    def var(self, cell: str) -> int:
        return self._var[cell]

    def cell(self, var: int) -> str:
        return self._cell[var]

    def is_primary(self, var: int) -> bool:
        return var in self._cell

    def literal(self, cell: str, who: str = CRIMINAL) -> int:
        """Trả về literal mang giá trị True khi ``cell`` có trạng thái ``who``."""
        v = self._var[cell]
        return v if who == CRIMINAL else -v

    def items(self):
        return self._var.items()


@dataclass
class CNF:
    """Kho lưu trữ mệnh đề CNF kèm bộ cấp phát biến phụ trợ."""

    num_primary: int
    clauses: list[list[int]] = field(default_factory=list)
    num_vars: int = 0
    origins: list[str] = field(default_factory=list)  # Lưu nguồn gốc sinh của từng mệnh đề

    def __post_init__(self) -> None:
        self.num_vars = max(self.num_vars, self.num_primary)
        self._tag = ""

    @property
    def num_aux(self) -> int:
        """Số lượng biến phụ đã được cấp phát thêm (đánh số sau các biến chính)."""
        return self.num_vars - self.num_primary

    def new_var(self) -> int:
        """Cấp phát một biến phụ mới."""
        self.num_vars += 1
        return self.num_vars

    def set_tag(self, tag: str) -> None:
        self._tag = tag

    def add(self, clause: Iterable[Term]) -> None:
        """Thêm một mệnh đề vào CNF, tự động giản lược hằng True/False, literal trùng và hằng đúng."""
        lits: list[int] = []
        for t in clause:
            if t is True:
                return  # Mệnh đề chắc chắn đúng
            if t is False:
                continue  # Literal False bị loại bỏ khỏi phép tuyển
            lits.append(t)

        seen: set[int] = set()
        out: list[int] = []
        for lit in lits:
            if -lit in seen:
                return  # Chứa đồng thời x và -x => tautology
            if lit not in seen:
                seen.add(lit)
                out.append(lit)
        self.clauses.append(out)
        self.origins.append(self._tag)

    # ----------------------------------------------------- Các cổng logic Tseitin
    def gate_and(self, a: Term, b: Term) -> Term:
        """Mã hóa ``z <-> (a & b)`` (lan truyền hằng trực tiếp nếu một vế là True/False)."""
        if a is False or b is False:
            return False
        if a is True:
            return b
        if b is True:
            return a
        if a == b:
            return a
        if a == -b:
            return False
        z = self.new_var()
        self.add([-z, a])
        self.add([-z, b])
        self.add([z, -a, -b])
        return z

    def gate_or(self, a: Term, b: Term) -> Term:
        """Mã hóa ``z <-> (a | b)``."""
        if a is True or b is True:
            return True
        if a is False:
            return b
        if b is False:
            return a
        if a == b:
            return a
        if a == -b:
            return True
        z = self.new_var()
        self.add([z, -a])
        self.add([z, -b])
        self.add([-z, a, b])
        return z

    def gate_xor(self, a: Term, b: Term) -> Term:
        """Mã hóa ``z <-> (a ^ b)`` dùng tối đa 4 mệnh đề CNF."""
        if isinstance(a, bool) and isinstance(b, bool):
            return a != b
        if a is False:
            return b
        if b is False:
            return a
        if a is True:
            return -b  # type: ignore[operator]
        if b is True:
            return -a  # type: ignore[operator]
        if a == b:
            return False
        if a == -b:
            return True
        z = self.new_var()
        self.add([-z, a, b])
        self.add([-z, -a, -b])
        self.add([z, -a, b])
        self.add([z, a, -b])
        return z

    def assert_term(self, t: Term, value: bool = True) -> None:
        """Ép một literal hoặc hằng phải bằng ``value`` (nếu trái hằng thì thêm mệnh đề rỗng)."""
        if isinstance(t, bool):
            if t != value:
                self.add([])
            return
        self.add([t if value else -t])


# ------------------------------------------------- Mã hóa ràng buộc đếm (Cardinality)
def unary_counter(cnf: CNF, lits: Sequence[int], upto: int) -> list[Term]:
    """Dựng bộ đếm tuần tự trả về danh sách ``r`` sao cho ``r[j] <-> (sum(lits) >= j)`` với ``j = 0..upto``.

    ``r[0]`` luôn là True; các chỉ số vượt quá ``len(lits)`` được rút gọn thành False.
    """
    upto = max(0, upto)
    prev: list[Term] = [True] + [False] * upto
    for x in lits:
        cur: list[Term] = [True]
        for j in range(1, upto + 1):
            cur.append(cnf.gate_or(prev[j], cnf.gate_and(x, prev[j - 1])))
        prev = cur
    return prev


def encode_at_most(cnf: CNF, lits: Sequence[int], k: int, mode: str = "auto") -> None:
    """Mã hóa ràng buộc tổng số literal đúng <= k."""
    n = len(lits)
    if k >= n:
        return
    if k < 0:
        cnf.add([])
        return
    if _use_direct(mode, n, k + 1):
        for subset in combinations(lits, k + 1):
            cnf.add([-x for x in subset])
    else:
        r = unary_counter(cnf, lits, k + 1)
        cnf.assert_term(r[k + 1], False)


def encode_at_least(cnf: CNF, lits: Sequence[int], k: int, mode: str = "auto") -> None:
    """Mã hóa ràng buộc tổng số literal đúng >= k."""
    n = len(lits)
    if k <= 0:
        return
    if k > n:
        cnf.add([])
        return
    if _use_direct(mode, n, n - k + 1):
        for subset in combinations(lits, n - k + 1):
            cnf.add(list(subset))
    else:
        r = unary_counter(cnf, lits, k)
        cnf.assert_term(r[k], True)


def _use_direct(mode: str, n: int, subset_size: int) -> bool:
    """Quyết định dùng tổ hợp trực tiếp hay bộ đếm tuần tự dựa trên mode và C(n, subset_size)."""
    if mode == "direct":
        return comb(n, subset_size) <= DIRECT_HARD_LIMIT
    if mode == "counter":
        return False
    return comb(n, subset_size) <= DIRECT_CLAUSE_LIMIT


# -------------------------------------------------------------- Bộ mã hóa ClueEncoder
class ClueEncoder:
    """Chuyển đổi các đối tượng :class:`Clue` hợp lệ thành các mệnh đề CNF."""

    def __init__(self, varmap: VarMap, cardinality: str = "auto"):
        if cardinality not in CARDINALITY_MODES:
            raise ValueError(f"cardinality must be one of {CARDINALITY_MODES}")
        self.varmap = varmap
        self.mode = cardinality

    def _lits(self, cells: Iterable[str], who: str) -> list[int]:
        return [self.varmap.literal(c, who) for c in cells]

    def encode(self, cnf: CNF, clue: Clue) -> None:
        """Sinh các mệnh đề CNF tương đương ngữ nghĩa với ``clue`` và thêm vào ``cnf``."""
        p, t = clue.params, clue.type
        vm = self.varmap
        if t == "FACT":
            cnf.add([vm.literal(p["cell"], p["status"])])
        elif t == "SAME":  # a <-> b  ==  (-a v b) & (a v -b)
            a, b = vm.var(p["a"]), vm.var(p["b"])
            cnf.add([-a, b])
            cnf.add([a, -b])
        elif t == "DIFFERENT":  # a xor b  ==  (a v b) & (-a v -b)
            a, b = vm.var(p["a"]), vm.var(p["b"])
            cnf.add([a, b])
            cnf.add([-a, -b])
        elif t == "EXACTLY":
            lits = self._lits(p["region"], p["who"])
            encode_at_least(cnf, lits, p["k"], self.mode)
            encode_at_most(cnf, lits, p["k"], self.mode)
        elif t == "AT_LEAST":
            encode_at_least(cnf, self._lits(p["region"], p["who"]), p["k"], self.mode)
        elif t == "AT_MOST":
            encode_at_most(cnf, self._lits(p["region"], p["who"]), p["k"], self.mode)
        elif t == "PARITY":
            self._parity(cnf, self._lits(p["region"], p["who"]), p["parity"] == "odd")
        elif t == "COMPARE":
            self._compare(cnf, self._lits(p["left"], p["who"]), self._lits(p["right"], p["who"]), p["op"])
        elif t == "CONNECTED":
            # Đoạn thẳng có thứ tự l_1..l_m không được có "lỗ": với mọi i < j < k thì (l_i & l_k) -> l_j
            lits = self._lits(p["region"], p["who"])
            for i in range(len(lits)):
                for k in range(i + 2, len(lits)):
                    for j in range(i + 1, k):
                        cnf.add([-lits[i], -lits[k], lits[j]])
        elif t == "IMPLIES":  # premise -> conclusion  ==  -premise v conclusion
            (ca, sa), (cb, sb) = p["if"], p["then"]
            cnf.add([-vm.literal(ca, sa), vm.literal(cb, sb)])
        else:
            raise ValueError(f"no encoder for clue type {t}")

    @staticmethod
    def _parity(cnf: CNF, lits: Sequence[int], odd: bool) -> None:
        """Chuỗi XOR Tseitin p_i = p_{i-1} ^ x_i, sau đó ép p_n bằng giá trị lẻ/chẵn."""
        acc: Term = False
        for x in lits:
            acc = cnf.gate_xor(acc, x)
        cnf.assert_term(acc, odd)

    @staticmethod
    def _compare(cnf: CNF, left: Sequence[int], right: Sequence[int], op: str) -> None:
        """So sánh số lượng giữa hai vùng bằng bộ đếm tuần tự L[j] <-> |left| >= j và R[j] <-> |right| >= j."""
        if op == "fewer":
            left, right, op = right, left, "more"
        size = max(len(left), len(right)) + 1
        lc = unary_counter(cnf, left, size)
        rc = unary_counter(cnf, right, size)
        if op == "equal":
            for j in range(1, size + 1):
                # L[j] <-> R[j]
                cnf.add([_neg(lc[j]), rc[j]])
                cnf.add([lc[j], _neg(rc[j])])
        else:  # more: |left| > |right| <=> với mọi j >= 0 thì R[j] -> L[j+1]
            for j in range(0, size):
                cnf.add([_neg(rc[j]), lc[j + 1]])


def _neg(t: Term) -> Term:
    """Phủ định một Term (literal nguyên hoặc hằng bool)."""
    if isinstance(t, bool):
        return not t
    return -t
