"""
Tác tử suy luận logic diễn dịch (Deductive Logic Agent).
Chỉ tương tác độc quyền với trạng thái tri thức công khai (PublicState).
Tuyệt đối không truy cập đáp án ẩn hay manh mối chưa được mở của GameEngine.
Tuân thủ nguyên tắc cốt lõi: KHÔNG ĐOÁN MÒ (NEVER GUESS).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .cnf import CNFEncoder, EncodedKB
from .dpll import DPLLSolver
from .models import Clue, Deduction, PublicState, SolverStats, Verdict
from .regions import cell_to_coord


@dataclass(frozen=True)
class Classification:
    """Kết quả phân loại suy luận logic cho toàn bộ các nhân vật chưa giải dưới KB_t."""
    verdicts: Mapping[str, Deduction]
    encoded: EncodedKB
    is_inconsistent: bool
    total_stats: SolverStats


class LogicAgent:
    """Tác tử suy luận diễn dịch thuần túy dựa trên bộ giải SAT DPLL."""

    def classify_all(self, state: PublicState) -> Classification:
        """Phân loại mọi nhân vật chưa giải dưới Knowledge Base hiện tại KB_t:
        - CRIMINAL: Nếu KB_t & NOT Ci là UNSAT
        - INNOCENT: Nếu KB_t & Ci là UNSAT
        - UNKNOWN: Nếu cả hai trường hợp đều SAT (chưa thể kết luận)
        - INCONSISTENT: Nếu chính bản thân KB_t là UNSAT"""
        encoder = CNFEncoder(state.characters)
        encoded = encoder.encode_public(state)

        # 1. Kiểm tra tính nhất quán cơ bản của KB_t
        base_test = DPLLSolver().solve(encoded.clauses, encoded.total_variables)
        if not base_test.satisfiable:
            inconsistent_deductions = {
                cell: Deduction(
                    cell=cell,
                    verdict=Verdict.INCONSISTENT,
                    queries=("KB_t |= FALSE (Cơ sở tri thức bị mâu thuẫn)",),
                    stats=base_test.stats,
                )
                for cell in encoder.variable_map
                if cell not in state.known_verdicts
            }
            return Classification(
                verdicts=inconsistent_deductions,
                encoded=encoded,
                is_inconsistent=True,
                total_stats=base_test.stats,
            )

        deductions: dict[str, Deduction] = {}
        total_stats = base_test.stats

        # 2. Kiểm tra hệ quả logic bắt buộc cho từng nhân vật chưa được giải
        for cell in self._row_major_cells(state):
            if cell in state.known_verdicts:
                continue

            var = encoded.variable_map[cell]

            # Kiểm tra xem có bắt buộc là CRIMINAL: KB_t |= Ci  <=>  KB_t & NOT Ci là UNSAT
            crm_res = DPLLSolver().solve(encoded.clauses, encoded.total_variables, assumptions=(-var,))
            # Kiểm tra xem có bắt buộc là INNOCENT: KB_t |= NOT Ci  <=>  KB_t & Ci là UNSAT
            inn_res = DPLLSolver().solve(encoded.clauses, encoded.total_variables, assumptions=(var,))

            step_stats = crm_res.stats.plus(inn_res.stats)
            total_stats = total_stats.plus(step_stats)

            queries = (
                f"KB_t & NOT {cell} = {'SAT' if crm_res.satisfiable else 'UNSAT'}",
                f"KB_t & {cell} = {'SAT' if inn_res.satisfiable else 'UNSAT'}",
            )

            if not crm_res.satisfiable:
                verdict = Verdict.CRIMINAL
            elif not inn_res.satisfiable:
                verdict = Verdict.INNOCENT
            else:
                verdict = Verdict.UNKNOWN

            deductions[cell] = Deduction(
                cell=cell,
                verdict=verdict,
                queries=queries,
                stats=step_stats,
            )

        return Classification(
            verdicts=deductions,
            encoded=encoded,
            is_inconsistent=False,
            total_stats=total_stats,
        )

    def next_forced(self, state: PublicState) -> Deduction | None:
        """Tìm bước đi bị ép buộc (forced) tiếp theo theo thứ tự hàng-cột xác định.
        Trả về None nếu không còn ô nào có thể chứng minh được mà không đoán mò."""
        classification = self.classify_all(state)
        if classification.is_inconsistent:
            return next(iter(classification.verdicts.values()), None)

        for cell in self._row_major_cells(state):
            deduction = classification.verdicts.get(cell)
            if deduction and deduction.verdict in (Verdict.CRIMINAL, Verdict.INNOCENT):
                return deduction
        return None

    def get_hint(self, state: PublicState) -> tuple[Clue | None, Deduction | None]:
        """Cung cấp gợi ý chỉ từ trạng thái công khai:
        Xác định một ô có thể chứng minh tiếp theo và manh mối công khai liên quan."""
        forced = self.next_forced(state)
        if not forced:
            return None, None

        target_cell = forced.cell
        # Tìm manh mối công khai có nhắc đến ô mục tiêu này
        relevant_clue: Clue | None = None
        for clue in state.revealed_clues:
            if target_cell in clue.targets or target_cell in clue.region or target_cell in clue.region_b:
                relevant_clue = clue
                break

        return relevant_clue, forced

    @staticmethod
    def _row_major_cells(state: PublicState) -> list[str]:
        """Sắp xếp các ô có tính xác định theo thứ tự hàng rồi cột: A1, B1, C1, A2, B2..."""
        return sorted(
            [char.cell for char in state.characters],
            key=lambda cell: (cell_to_coord(cell)[1], cell_to_coord(cell)[0]),
        )
