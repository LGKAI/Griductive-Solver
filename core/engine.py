"""
Bộ điều hành trò chơi (GameEngine).
Nắm giữ dữ liệu bí mật của câu đố (đáp án ẩn, manh mối chưa mở).
Thực thi giao thức suy luận không đoán mò, đảm bảo tác tử LogicAgent
chỉ nhận trạng thái công khai PublicState và thực hiện kiểm tra tính duy nhất (Uniqueness check).
"""
from __future__ import annotations

from typing import Sequence

from .agent import LogicAgent
from .clues import evaluate_clue, validate_clue
from .cnf import CNFEncoder
from .dpll import DPLLSolver
from .models import (
    Deduction,
    PublicState,
    Puzzle,
    SolverStats,
    Status,
    SubmissionResult,
    TraceEntry,
    Verdict,
)
from .regions import cell_to_coord


class GameEngine:
    """Bộ máy trò chơi kiểm soát luật chơi và bảo vệ tính toàn vẹn của dữ liệu ẩn."""

    def __init__(self, puzzle: Puzzle):
        self.puzzle = puzzle
        self._validate_puzzle()
        self.restart()

    def restart(self) -> None:
        """Đặt lại ván chơi về trạng thái ban đầu chỉ với các thẻ được mở mặt sẵn."""
        self._known: dict[str, Status] = {
            cell: self.puzzle.solution[cell] for cell in self.puzzle.initially_revealed
        }
        self._revealed: set[str] = set(self.puzzle.initially_revealed)
        self.trace: list[TraceEntry] = []

    def public_state(self) -> PublicState:
        """Tạo trạng thái tri thức công khai cho người chơi và tác tử.
        Tuyệt đối không tiết lộ đáp án ẩn hoặc manh mối chưa được lật."""
        revealed_clues = tuple(
            self.puzzle.clues[cell]
            for cell in sorted(self._revealed, key=lambda c: (cell_to_coord(c)[1], cell_to_coord(c)[0]))
        )
        return PublicState(
            puzzle_id=self.puzzle.id,
            rows=self.puzzle.rows,
            columns=self.puzzle.columns,
            characters=self.puzzle.characters,
            revealed_clues=revealed_clues,
            known_verdicts=dict(self._known),
        )

    def submit(self, cell: str, proposed: Status, agent: LogicAgent) -> SubmissionResult:
        """Xử lý nộp phán đoán cho một ô chưa giải.
        Kiểm tra hệ quả logic từ KB_t thông qua tác tử:
        - Nếu chứng minh được và khớp với phán đoán -> ACCEPTED, lật thẻ và lộ manh mối mới.
        - Nếu cả hai trạng thái đều có thể xảy ra -> NOT_PROVABLE (từ chối).
        - Nếu trạng thái ngược lại là bắt buộc -> CONTRADICTED (từ chối)."""
        if cell in self._known:
            return SubmissionResult.ALREADY_SOLVED
        if cell not in self.puzzle.solution:
            raise ValueError(f"Tọa độ ô không xác định: '{cell}'.")

        classification = agent.classify_all(self.public_state())
        return self._process_verdict(cell, proposed, classification)

    def _process_verdict(self, cell: str, proposed: Status, classification) -> SubmissionResult:
        deduction: Deduction = classification.verdicts[cell]

        if deduction.verdict is Verdict.INCONSISTENT:
            return SubmissionResult.INCONSISTENT

        if deduction.verdict is Verdict.UNKNOWN:
            # Chưa đủ cơ sở logic: Từ chối mà không thay đổi trạng thái ván chơi
            return SubmissionResult.NOT_PROVABLE

        forced_status = Status(deduction.verdict.value)
        if forced_status is not proposed:
            # Trạng thái ngược lại mới là bắt buộc: Từ chối
            return SubmissionResult.CONTRADICTED

        # Xác thực tính toàn vẹn: Kết luận logic phải trùng khớp với đáp án ẩn
        if self.puzzle.solution[cell] is not forced_status:
            raise RuntimeError(
                f"Lỗi toàn vẹn: Kết luận chứng minh cho {cell} ({forced_status}) khác đáp án ẩn ({self.puzzle.solution[cell]})."
            )

        # Chấp nhận phán đoán, đánh dấu trạng thái và lật thẻ
        self._known[cell] = forced_status
        self._revealed.add(cell)

        # Ghi nhận bản ghi nhật ký suy luận
        active_clue_ids = tuple(
            clue.id for clue in self.public_state().revealed_clues if clue.owner != cell
        )
        self.trace.append(
            TraceEntry(
                step=len(self.trace) + 1,
                active_clue_ids=active_clue_ids,
                cell=cell,
                verdict=deduction.verdict,
                sat_queries=deduction.queries,
                revealed_clue_id=self.puzzle.clues[cell].id,
                stats=classification.total_stats,
            )
        )
        return SubmissionResult.ACCEPTED

    def auto_step(self, agent: LogicAgent) -> tuple[SubmissionResult, Deduction | None]:
        """Tự động tìm kiếm và thực hiện bước suy luận bắt buộc tiếp theo theo thứ tự hàng-cột."""
        classification = agent.classify_all(self.public_state())
        if classification.is_inconsistent:
            return SubmissionResult.INCONSISTENT, next(iter(classification.verdicts.values()), None)

        ordered_cells = sorted(
            [char.cell for char in self.puzzle.characters],
            key=lambda c: (cell_to_coord(c)[1], cell_to_coord(c)[0]),
        )

        forced_deduction: Deduction | None = None
        for cell in ordered_cells:
            if cell in classification.verdicts and classification.verdicts[cell].verdict in (
                Verdict.CRIMINAL,
                Verdict.INNOCENT,
            ):
                forced_deduction = classification.verdicts[cell]
                break

        if forced_deduction is None:
            return SubmissionResult.NOT_PROVABLE, None

        result = self._process_verdict(
            forced_deduction.cell,
            Status(forced_deduction.verdict.value),
            classification,
        )
        return result, forced_deduction

    def is_solved(self) -> bool:
        """Kiểm tra xem toàn bộ các nhân vật trên bàn cờ đã được giải quyết hết chưa."""
        return len(self._known) == len(self.puzzle.characters)

    def uniqueness_check(self) -> tuple[bool, SolverStats]:
        """Kiểm tra xem toàn bộ tập manh mối có đảm bảo nghiệm duy nhất hay không:
        1. Mã hóa toàn bộ manh mối (không kèm 2 thẻ mở sẵn ban đầu).
        2. Dùng DPLL tìm nghiệm M1. Nếu UNSAT -> Vô nghiệm.
        3. Tạo mệnh đề chặn ~M1 và giải lại bằng DPLL -> Nghiệm M2.
        4. Nếu M2 là UNSAT -> Bài toán có NGHIỆM DUY NHẤT."""
        all_clues_state = PublicState(
            puzzle_id=self.puzzle.id,
            rows=self.puzzle.rows,
            columns=self.puzzle.columns,
            characters=self.puzzle.characters,
            revealed_clues=tuple(self.puzzle.clues.values()),
            known_verdicts={},
        )
        encoder = CNFEncoder(all_clues_state.characters)
        encoded = encoder.encode_public(all_clues_state)

        # 1. Tìm mô hình thỏa mãn đầu tiên
        first_res = DPLLSolver().solve(encoded.clauses, encoded.total_variables)
        if not first_res.satisfiable or first_res.assignment is None:
            return False, first_res.stats

        # 2. Xây dựng mệnh đề chặn phủ định mô hình M1
        blocking_clause = tuple(
            -var if first_res.assignment[var] else var
            for var in range(1, encoded.primary_variables + 1)
        )

        # 3. Giải lại khi đã thêm mệnh đề chặn
        second_res = DPLLSolver().solve(
            encoded.clauses + (blocking_clause,),
            encoded.total_variables,
        )

        # Nếu lần giải thứ 2 là UNSAT, chứng tỏ M1 là nghiệm DUY NHẤT
        is_unique = not second_res.satisfiable
        total_stats = first_res.stats.plus(second_res.stats)
        return is_unique, total_stats

    def _validate_puzzle(self) -> None:
        """Kiểm tra cấu trúc và tính hợp lệ của câu đố."""
        cells = {char.cell for char in self.puzzle.characters}
        if not (3 <= self.puzzle.rows <= 5) or not (3 <= self.puzzle.columns <= 5):
            raise ValueError(f"Kích thước bàn cờ phải nằm trong [3, 5], nhận {self.puzzle.rows}x{self.puzzle.columns}.")

        if len(cells) != self.puzzle.rows * self.puzzle.columns:
            raise ValueError("Số lượng nhân vật không khớp với số hàng * số cột.")

        if set(self.puzzle.clues.keys()) != cells or set(self.puzzle.solution.keys()) != cells:
            raise ValueError("Mỗi ô trên bàn cờ phải có đúng 1 manh mối và 1 trạng thái đáp án.")

        for cell, clue in self.puzzle.clues.items():
            if clue.owner != cell:
                raise ValueError(f"Không khớp ô sở hữu manh mối tại ô {cell}.")
            validate_clue(clue, cells)
            if not evaluate_clue(clue, self.puzzle.solution):
                raise ValueError(f"Manh mối {clue.id} tại {cell} sai so với đáp án ẩn.")

        if not set(self.puzzle.initially_revealed).issubset(cells):
            raise ValueError("Tọa độ thẻ mở sẵn ban đầu không nằm trên bàn cờ.")
