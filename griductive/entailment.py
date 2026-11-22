"""Phân loại hệ quả logic (Entailment), gợi ý tối thiểu (Hint) và kiểm tra nghiệm duy nhất.

Đối với một nhân vật ``i`` chưa giải tại bước ``t``:

    KB_t |= C_i   <=>  KB_t AND NOT C_i  là UNSAT   ->  CRIMINAL
    KB_t |= -C_i  <=>  KB_t AND C_i      là UNSAT   ->  INNOCENT
    cả hai đều SAT                                  ->  UNKNOWN (không đoán)
    chính KB_t là UNSAT                             ->  INCONSISTENT

Hai chiến lược truy vấn cho kết quả phân loại giống hệt nhau:

* ``naive``  - Hai truy vấn SAT cho mỗi ô chưa biết.
* ``filter`` - Lọc mô hình: giải KB_t một lần để lấy mô hình M; với mỗi ô chưa biết i,
  chỉ hỏi ``KB_t AND (C_i != M_i)``. Nếu UNSAT thì i bị ép bằng M_i. Nếu SAT, mô hình
  mới M' cho thấy mọi ô j có M'_j != M_j đều là UNKNOWN nên không cần truy vấn lại.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

from .board import Board
from .clues import Clue
from .dpll import DPLLSolver, SolverStats
from .knowledge import KnowledgeBase, PublicState, build_kb, build_public_kb

CRIMINAL_V = "CRIMINAL"
INNOCENT_V = "INNOCENT"
UNKNOWN_V = "UNKNOWN"
INCONSISTENT_V = "INCONSISTENT"

STRATEGIES = ("filter", "naive")


@dataclass
class SatQuery:
    """Thông tin một lượt gọi DPLL để ghi vào nhật ký Trace và hiển thị trên UI."""

    label: str  # Ví dụ: "KB ∧ ¬C(B2)"
    cell: Optional[str]
    assumed_criminal: Optional[bool]
    result: str  # SAT / UNSAT
    stats: dict

    def to_dict(self) -> dict:
        return {"query": self.label, "cell": self.cell, "assumed_criminal": self.assumed_criminal,
                "result": self.result, **self.stats}


@dataclass
class Analysis:
    """Kết quả phân loại toàn bộ các ô chưa biết tại trạng thái công khai hiện tại."""

    consistent: bool
    classification: dict[str, str]  # cell chưa biết -> CRIMINAL / INNOCENT / UNKNOWN
    queries: list[SatQuery]
    kb_stats: dict
    solver: SolverStats = field(default_factory=SolverStats)

    @property
    def forced(self) -> list[tuple[str, str]]:
        """Các cặp (ô, phán đoán bắt buộc) theo thứ tự row-major."""
        return [(c, v) for c, v in self.classification.items() if v in (CRIMINAL_V, INNOCENT_V)]

    @property
    def sat_calls(self) -> int:
        return len(self.queries)


def _query_label(cell: str, criminal: bool) -> str:
    return f"KB ∧ {'' if criminal else '¬'}C({cell})"


def analyze(state: PublicState, strategy: str = "filter", cardinality: str = "auto",
            time_limit: Optional[float] = None) -> Analysis:
    """Phân loại tất cả các nhân vật chưa biết từ trạng thái công khai ``state``."""
    kb = build_public_kb(state, cardinality)
    return analyze_kb(kb, state.unknown_cells, strategy, time_limit)


def analyze_kb(kb: KnowledgeBase, cells: Iterable[str], strategy: str = "filter",
               time_limit: Optional[float] = None) -> Analysis:
    """Chạy kiểm tra kéo theo trên ``kb`` cho danh sách ô ``cells`` bằng chiến lược ``filter`` hoặc ``naive``."""
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}")
    cells = list(cells)
    solver = DPLLSolver(kb.cnf.num_vars, kb.cnf.clauses)
    total = SolverStats()
    queries: list[SatQuery] = []

    def run(label: str, cell: Optional[str], assume: Optional[bool]):
        assumptions = [] if cell is None else [kb.varmap.var(cell) if assume else -kb.varmap.var(cell)]
        res = solver.solve(assumptions, time_limit)
        total.add(res.stats)
        queries.append(SatQuery(label, cell, assume, res.status, res.stats.to_dict()))
        return res

    # Bước 1: Kiểm tra tính nhất quán của bản thân KB_t trước khi xét từng ô
    base = run("KB", None, None)
    if not base.sat:
        return Analysis(False, {c: INCONSISTENT_V for c in cells}, queries, kb.stats, total)

    classification: dict[str, str] = {}
    if strategy == "naive":
        for cell in cells:
            can_be_innocent = run(_query_label(cell, False), cell, False).sat
            can_be_criminal = run(_query_label(cell, True), cell, True).sat
            classification[cell] = _verdict(can_be_criminal, can_be_innocent)
        return Analysis(True, classification, queries, kb.stats, total)

    # Chiến lược 'filter': dựa trên mô hình gốc M để loại sớm các ô chắc chắn UNKNOWN
    model = base.model
    var = kb.varmap.var
    unknown: set[str] = set()
    for cell in cells:
        if cell in unknown:
            classification[cell] = UNKNOWN_V
            continue
        value = model[var(cell)]
        res = run(_query_label(cell, not value), cell, not value)
        if not res.sat:
            classification[cell] = CRIMINAL_V if value else INNOCENT_V
        else:
            classification[cell] = UNKNOWN_V
            # Mọi ô có giá trị khác nhau giữa M và M' đều tồn tại cả 2 khả năng -> UNKNOWN
            for other in cells:
                if res.model[var(other)] != model[var(other)]:
                    unknown.add(other)
    return Analysis(True, classification, queries, kb.stats, total)


def _verdict(can_be_criminal: bool, can_be_innocent: bool) -> str:
    if can_be_criminal and can_be_innocent:
        return UNKNOWN_V
    if can_be_criminal:
        return CRIMINAL_V
    if can_be_innocent:
        return INNOCENT_V
    return INCONSISTENT_V


def is_entailed(board: Board, clues: Iterable[Clue], verdicts: Mapping[str, bool], cell: str,
                criminal: bool, cardinality: str = "auto") -> bool:
    """Trả về True nếu và chỉ nếu tập manh mối + phán đoán đã có ép buộc trạng thái cho ``cell``."""
    kb = build_kb(board, clues, verdicts, cardinality)
    lit = kb.varmap.var(cell)
    return not DPLLSolver(kb.cnf.num_vars, kb.cnf.clauses).solve([-lit if criminal else lit]).sat


def minimal_support(state: PublicState, cell: str, criminal: bool, cardinality: str = "auto") -> list[str]:
    """Trích xuất tập con manh mối đã mở tối thiểu (theo quan hệ bao hàm) đủ để chứng minh ``cell``."""
    support = list(state.revealed_clues)
    if not is_entailed(state.board, support, state.verdicts, cell, criminal, cardinality):
        return []
    i = 0
    while i < len(support):
        trial = support[:i] + support[i + 1:]
        if is_entailed(state.board, trial, state.verdicts, cell, criminal, cardinality):
            support = trial
        else:
            i += 1
    return [c.clue_id for c in support]


# ------------------------------------------------------ Kiểm tra nghiệm duy nhất
@dataclass
class UniquenessResult:
    """Kết quả kiểm tra số nghiệm trên tập manh mối đầy đủ (tối đa ``limit`` nghiệm)."""

    count: int
    solutions: list[dict[str, bool]]
    sat_calls: int
    stats: SolverStats

    @property
    def unique(self) -> bool:
        return self.count == 1

    @property
    def verdict(self) -> str:
        if self.count == 0:
            return "NO_SOLUTION"
        return "UNIQUE" if self.count == 1 else "MULTIPLE"


def check_uniqueness(board: Board, clues: Iterable[Clue], verdicts: Mapping[str, bool] | None = None,
                     limit: int = 2, cardinality: str = "auto",
                     time_limit: Optional[float] = None) -> UniquenessResult:
    """Đếm số nghiệm thỏa mãn toàn bộ tập manh mối (dừng khi đủ ``limit`` nghiệm).

    Mệnh đề chặn (blocking clause) chỉ phủ định các biến chính (1..N^2) để giá trị
    khác nhau của các biến phụ Tseitin không tạo ra nghiệm trùng giả.
    """
    kb = build_kb(board, clues, verdicts or {}, cardinality)
    clauses = [list(c) for c in kb.cnf.clauses]
    total = SolverStats()
    solutions: list[dict[str, bool]] = []
    calls = 0
    while len(solutions) < limit:
        res = DPLLSolver(kb.cnf.num_vars, clauses).solve(time_limit=time_limit)
        calls += 1
        total.add(res.stats)
        if not res.sat:
            break
        sol = {cell: res.model[kb.varmap.var(cell)] for cell in board.cells}
        solutions.append(sol)
        clauses.append([-kb.varmap.var(c) if v else kb.varmap.var(c) for c, v in sol.items()])
    return UniquenessResult(len(solutions), solutions, calls, total)
