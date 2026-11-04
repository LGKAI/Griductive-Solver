"""
Định nghĩa các cấu trúc dữ liệu và mô hình dùng trong trò chơi Griductive Solver.
Bao gồm: Trạng thái nhân vật, loại manh mối, kết luận suy luận, câu đố và thống kê bộ giải.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class Status(str, Enum):
    """Trạng thái ẩn hoặc đã biết của một nhân vật: Tội phạm (CRIMINAL) hoặc Vô tội (INNOCENT)."""
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"

    @property
    def boolean(self) -> bool:
        """Trả về True nếu là CRIMINAL (Ci = True), False nếu là INNOCENT (Ci = False)."""
        return self is Status.CRIMINAL

    @classmethod
    def from_boolean(cls, value: bool) -> Status:
        return cls.CRIMINAL if value else cls.INNOCENT


class ClueKind(str, Enum):
    """Các mẫu manh mối logic cốt lõi và các phần mở rộng."""
    # 6 mẫu manh mối cốt lõi
    FACT = "FACT"                  # Một người có trạng thái xác định
    SAME = "SAME"                  # Hai người có cùng trạng thái
    DIFFERENT = "DIFFERENT"        # Hai người có trạng thái khác nhau
    EXACTLY = "EXACTLY"            # Đúng k tội phạm trong một vùng
    AT_LEAST = "AT_LEAST"          # Ít nhất k tội phạm trong một vùng
    AT_MOST = "AT_MOST"            # Nhiều nhất k tội phạm trong một vùng
    # 2 phần mở rộng
    PARITY = "PARITY"              # Tính chẵn lẻ (EVEN / ODD) của số tội phạm trong vùng
    COUNT_COMPARE = "COUNT_COMPARE"# So sánh số lượng tội phạm giữa 2 vùng


class Verdict(str, Enum):
    """Kết luận suy luận logic đối với một nhân vật chưa giải."""
    CRIMINAL = "CRIMINAL"          # Bắt buộc là Criminal (KB & NOT Ci là UNSAT)
    INNOCENT = "INNOCENT"          # Bắt buộc là Innocent (KB & Ci là UNSAT)
    UNKNOWN = "UNKNOWN"            # Chưa thể xác định (cả 2 đều thỏa mãn SAT)
    INCONSISTENT = "INCONSISTENT"  # Xung đột logic (KB không thỏa mãn)


class SubmissionResult(str, Enum):
    """Kết quả phản hồi từ GameEngine khi người chơi hoặc tác tử nộp một phán đoán."""
    ACCEPTED = "ACCEPTED"              # Chấp nhận: Phán đoán đã được logic chứng minh bắt buộc
    NOT_PROVABLE = "NOT_PROVABLE"      # Từ chối: Cả hai trạng thái vẫn có thể xảy ra
    CONTRADICTED = "CONTRADICTED"      # Từ chối: Trạng thái ngược lại mới là đúng
    INCONSISTENT = "INCONSISTENT"      # Lỗi: Knowledge Base bị mâu thuẫn
    ALREADY_SOLVED = "ALREADY_SOLVED"  # Ô này đã được giải từ trước


@dataclass(frozen=True)
class Character:
    """Đại diện cho một nhân vật (cầu thủ) trên một ô bàn cờ."""
    cell: str                # Tọa độ ô, ví dụ: 'A1', 'B2'
    name: str                # Tên nhân vật, ví dụ: 'Messi', 'Ronaldo'
    profession: str          # Vị trí / Đội tuyển, ví dụ: 'Forward (Argentina)'
    portrait_index: int = 0  # Chỉ số ảnh chân dung (0 đến 24 trong lưới 5x5)


@dataclass(frozen=True)
class Clue:
    """Manh mối logic có cấu trúc được mang bởi một nhân vật."""
    id: str                                    # Mã định danh manh mối, ví dụ: 'CLUE-01'
    owner: str                                 # Tọa độ ô thẻ sở hữu manh mối này
    kind: ClueKind                             # Loại manh mối
    targets: tuple[str, ...] = ()              # Các ô mục tiêu tham chiếu (cho FACT, SAME, DIFFERENT)
    status: Status | None = None               # Trạng thái mục tiêu (dùng cho FACT)
    region_type: str = "EXPLICIT"              # Loại vùng: 'ROW', 'COLUMN', 'NEIGHBORS', 'EXPLICIT'
    region: tuple[str, ...] = ()               # Danh sách các ô thuộc vùng chính
    k: int | None = None                       # Số lượng đếm tội phạm (k)
    parity: str | None = None                  # 'EVEN' (chẵn) hoặc 'ODD' (lẻ)
    region_b: tuple[str, ...] = ()             # Vùng so sánh thứ hai (dùng cho COUNT_COMPARE)
    comparison: str | None = None              # Phép so sánh: 'EQ', 'GT', 'LT'


@dataclass(frozen=True)
class Puzzle:
    """Biểu diễn toàn bộ ván chơi câu đố, do GameEngine bảo mật độc quyền."""
    id: str
    title: str
    rows: int
    columns: int
    characters: tuple[Character, ...]
    clues: Mapping[str, Clue]                  # Tọa độ ô chủ sở hữu -> Manh mối
    solution: Mapping[str, Status]             # Tọa độ ô -> Đáp án ẩn
    initially_revealed: tuple[str, ...]        # Các thẻ được mở mặt sẵn ban đầu
    seed: int = 0

    @property
    def cell_count(self) -> int:
        return self.rows * self.columns


@dataclass(frozen=True)
class PublicState:
    """Trạng thái tri thức công khai cung cấp cho người chơi và LogicAgent.
    Tuyệt đối không chứa đáp án ẩn (solution) hay manh mối chưa được mở."""
    puzzle_id: str
    rows: int
    columns: int
    characters: tuple[Character, ...]
    revealed_clues: tuple[Clue, ...]           # Danh sách các manh mối đã lật
    known_verdicts: Mapping[str, Status]       # Danh sách các ô đã chứng minh được


@dataclass(frozen=True)
class SolverStats:
    """Thống kê chi tiết hiệu năng của bộ giải SAT DPLL."""
    sat_calls: int = 0                         # Số lần gọi giải SAT
    decisions: int = 0                         # Số lần quyết định rẽ nhánh
    propagations: int = 0                      # Số lần lan truyền mệnh đề đơn vị
    backtracks: int = 0                        # Số lần quay lui
    runtime_ms: float = 0.0                    # Thời gian thực thi (mili-giây)

    def plus(self, other: SolverStats) -> SolverStats:
        return SolverStats(
            self.sat_calls + other.sat_calls,
            self.decisions + other.decisions,
            self.propagations + other.propagations,
            self.backtracks + other.backtracks,
            self.runtime_ms + other.runtime_ms,
        )


@dataclass(frozen=True)
class Deduction:
    """Kết quả phân loại suy luận diễn dịch cho một nhân vật tại bước hiện tại."""
    cell: str
    verdict: Verdict
    queries: tuple[str, ...]
    stats: SolverStats


@dataclass(frozen=True)
class TraceEntry:
    """Bản ghi nhật ký chi tiết cho mỗi bước suy luận được chấp nhận."""
    step: int
    active_clue_ids: tuple[str, ...]
    cell: str
    verdict: Verdict
    sat_queries: tuple[str, ...]
    revealed_clue_id: str
    stats: SolverStats
