"""
Bộ giải bài toán thỏa mãn mệnh đề Boolean SAT dựa trên thủ tục DPLL
(Davis-Putnam-Logemann-Loveland).
Tự triển khai đầy đủ các thành phần:
1. Lan truyền mệnh đề đơn vị (Unit propagation)
2. Phát hiện xung đột (Conflict detection)
3. Chọn biến có tính xác định (Deterministic variable selection)
4. Rẽ nhánh đệ quy và quay lui theo thời gian (Chronological backtracking)
5. Trả về SAT kèm mô hình gán hoàn chỉnh hoặc UNSAT
6. Ghi nhận số liệu: decisions, propagations, backtracks, runtime
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Mapping, Sequence

from .cnf import Clause
from .models import SolverStats


@dataclass(frozen=True)
class SolveResult:
    """Kết quả trả về của bộ giải DPLLSolver."""
    satisfiable: bool
    assignment: Mapping[int, bool] | None
    stats: SolverStats


class DPLLSolver:
    """Bộ giải SAT DPLL tự cài đặt hoàn chỉnh bằng Python thuần."""

    def __init__(self) -> None:
        self.decisions: int = 0
        self.propagations: int = 0
        self.backtracks: int = 0

    def solve(
        self,
        clauses: Sequence[Clause],
        variable_count: int,
        assumptions: Sequence[int] = (),
    ) -> SolveResult:
        """Giải công thức CNF dưới các giả thiết gán tạm thời (assumptions).
        Trả về kết quả có thỏa mãn hay không, phép gán hoàn chỉnh và thống kê hiệu năng."""
        self.decisions = 0
        self.propagations = 0
        self.backtracks = 0
        start_time = perf_counter()

        initial_assignment: dict[int, bool] = {}

        # Áp dụng trực tiếp các giả thiết
        for lit in assumptions:
            var = abs(lit)
            val = (lit > 0)
            if var in initial_assignment and initial_assignment[var] != val:
                # Xung đột ngay trong chính tập giả thiết
                runtime_ms = (perf_counter() - start_time) * 1000
                return SolveResult(
                    satisfiable=False,
                    assignment=None,
                    stats=SolverStats(1, 0, 0, 0, runtime_ms),
                )
            initial_assignment[var] = val

        # Bắt đầu thủ tục tìm kiếm đệ quy DPLL
        final_model = self._dpll(tuple(clauses), variable_count, initial_assignment)
        runtime_ms = (perf_counter() - start_time) * 1000

        if final_model is not None:
            # Đảm bảo phép gán hoàn chỉnh cho toàn bộ biến từ 1 đến variable_count
            complete = dict(final_model)
            for v in range(1, variable_count + 1):
                if v not in complete:
                    complete[v] = False
            return SolveResult(
                satisfiable=True,
                assignment=complete,
                stats=SolverStats(1, self.decisions, self.propagations, self.backtracks, runtime_ms),
            )

        return SolveResult(
            satisfiable=False,
            assignment=None,
            stats=SolverStats(1, self.decisions, self.propagations, self.backtracks, runtime_ms),
        )

    def _dpll(
        self,
        clauses: tuple[Clause, ...],
        variable_count: int,
        assignment: dict[int, bool],
    ) -> dict[int, bool] | None:
        """Hàm đệ quy cốt lõi của thuật toán DPLL."""
        # 1. Lan truyền mệnh đề đơn vị & Phát hiện xung đột
        propagated_assignment = dict(assignment)
        if not self._unit_propagate(clauses, propagated_assignment):
            return None

        # 2. Kiểm tra nếu tất cả các biến đã được gán giá trị
        unassigned_vars = [v for v in range(1, variable_count + 1) if v not in propagated_assignment]
        if not unassigned_vars:
            return propagated_assignment

        # Kiểm tra xem toàn bộ các mệnh đề đã được thỏa mãn chưa
        all_satisfied = True
        for clause in clauses:
            if not self._is_clause_satisfied(clause, propagated_assignment):
                all_satisfied = False
                break
        if all_satisfied:
            return propagated_assignment

        # 3. Chọn biến có tính xác định: Chọn biến chưa gán có chỉ số nhỏ nhất
        chosen_var = min(unassigned_vars)

        # 4. Rẽ nhánh đệ quy và quay lui
        self.decisions += 1

        # Nhánh 1: Thử gán chosen_var = True
        branch_true = dict(propagated_assignment)
        branch_true[chosen_var] = True
        result = self._dpll(clauses, variable_count, branch_true)
        if result is not None:
            return result

        # Quay lui từ nhánh True
        self.backtracks += 1

        # Nhánh 2: Thử gán chosen_var = False
        branch_false = dict(propagated_assignment)
        branch_false[chosen_var] = False
        result = self._dpll(clauses, variable_count, branch_false)
        if result is not None:
            return result

        # Quay lui từ nhánh False
        self.backtracks += 1
        return None

    def _unit_propagate(
        self,
        clauses: tuple[Clause, ...],
        assignment: dict[int, bool],
    ) -> bool:
        """Lặp duyệt lan truyền mệnh đề đơn vị cho đến khi không còn mệnh đề đơn vị nào.
        Trả về False nếu gặp xung đột, True nếu an toàn."""
        changed = True
        while changed:
            changed = False
            for clause in clauses:
                is_sat, unit_lit = self._evaluate_clause(clause, assignment)
                if is_sat:
                    continue
                if unit_lit is None:
                    # Toàn bộ literal trong mệnh đề đều False -> Xung đột!
                    return False
                if unit_lit != 0:
                    # Tìm thấy mệnh đề đơn vị với literal bắt buộc gán
                    var = abs(unit_lit)
                    val = (unit_lit > 0)
                    if var in assignment:
                        if assignment[var] != val:
                            return False
                    else:
                        assignment[var] = val
                        self.propagations += 1
                        changed = True
        return True

    @staticmethod
    def _evaluate_clause(
        clause: Clause,
        assignment: Mapping[int, bool],
    ) -> tuple[bool, int | None]:
        """Đánh giá trạng thái của một mệnh đề dưới phép gán hiện tại:
        - (True, None): Mệnh đề đã thỏa mãn (có ít nhất 1 literal True).
        - (False, None): Mệnh đề xung đột (toàn bộ literal đều False).
        - (False, lit): Mệnh đề đơn vị với đúng 1 literal chưa gán là `lit`.
        - (False, 0): Mệnh đề mở (còn >= 2 literal chưa gán)."""
        unresolved_lits: list[int] = []
        for lit in clause:
            var = abs(lit)
            val = assignment.get(var)
            if val is None:
                unresolved_lits.append(lit)
            elif val == (lit > 0):
                return True, None

        if not unresolved_lits:
            return False, None
        if len(unresolved_lits) == 1:
            return False, unresolved_lits[0]
        return False, 0

    @staticmethod
    def _is_clause_satisfied(clause: Clause, assignment: Mapping[int, bool]) -> bool:
        """Kiểm tra xem một mệnh đề có ít nhất một literal nhận giá trị True hay không."""
        for lit in clause:
            var = abs(lit)
            val = assignment.get(var)
            if val is not None and val == (lit > 0):
                return True
        return False
