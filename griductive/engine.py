"""Game Engine: nắm giữ toàn bộ câu đố, đáp án ẩn và các manh mối chưa mở.

Engine chỉ cung cấp ảnh chụp bất biến :class:`PublicState` cho người chơi và tác tử.
Mọi phán đoán chỉ được chấp nhận khi được kéo theo logic từ Cơ sở tri thức công khai;
đáp án ẩn chỉ dùng làm lớp kiểm tra an toàn cuối cùng và để mở thẻ/manh mối kế tiếp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .clues import Clue
from .entailment import (CRIMINAL_V, INNOCENT_V, Analysis, UniquenessResult, analyze,
                         check_uniqueness)
from .knowledge import PublicCharacter, PublicState
from .puzzle import Puzzle

ACCEPTED = "ACCEPTED"
NOT_PROVABLE = "NOT_PROVABLE"
CONTRADICTED = "CONTRADICTED"
ALREADY_KNOWN = "ALREADY_KNOWN"
INVALID = "INVALID"
INCONSISTENT = "INCONSISTENT"
GAME_OVER = "GAME_OVER"

PLAYING = "PLAYING"
SOLVED = "SOLVED"
LOST = "LOST"  # Phán đoán CONTRADICTED đã kết thúc ván chơi (sudden death)


class PuzzleIntegrityError(RuntimeError):
    """Ngoại lệ khi phán đoán kéo theo hợp lệ từ manh mối lại trái với đáp án lưu trong tệp."""


@dataclass
class SubmitResult:
    """Kết quả thẩm định một phán đoán do người chơi hoặc LogicAgent gửi lên."""

    status: str
    cell: str
    verdict: str
    message: str
    revealed_clue: Optional[Clue] = None

    @property
    def accepted(self) -> bool:
        return self.status == ACCEPTED


@dataclass
class GameEngine:
    """Bộ điều phối trò chơi bảo mật: tách biệt hoàn toàn đáp án ẩn khỏi người chơi và tác tử."""

    puzzle: Puzzle
    strategy: str = "filter"
    cardinality: str = "auto"
    verdicts: dict[str, bool] = field(default_factory=dict)
    revealed: list[str] = field(default_factory=list)  # Danh sách ô đã mở thẻ/manh mối
    sudden_death: bool = True  # Phán đoán CONTRADICTED sẽ kết thúc ván ngay lập tức
    lost: Optional[tuple[str, str]] = None  # Cặp (cell, verdict) đã làm kết thúc ván chơi
    version: int = 0
    sat_calls: int = 0  # Số lần gọi SAT mà chính Engine dùng để thẩm định phán đoán
    _cache: Optional[tuple[int, Analysis]] = field(default=None, repr=False)
    _charged: Optional[int] = field(default=None, repr=False)  # Tránh tính trùng sat_calls trên cùng 1 KB version

    def __post_init__(self) -> None:
        self.reset()

    # ------------------------------------------------------------ Quản lý trạng thái
    def reset(self) -> None:
        """Đưa bàn cờ về trạng thái mở sẵn ban đầu."""
        self.verdicts = {c: self.puzzle.solution[c] for c in self.puzzle.initial}
        self.revealed = list(self.puzzle.initial)
        self.lost = None
        self.sat_calls = 0
        self.version += 1
        self._cache = None
        self._charged = None

    @property
    def board(self):
        return self.puzzle.board

    @property
    def status(self) -> str:
        if self.lost is not None:
            return LOST
        return SOLVED if len(self.verdicts) == len(self.board.cells) else PLAYING

    def public_state(self) -> PublicState:
        """Tạo snapshot công khai an toàn — không bao gồm solution hoặc manh mối ẩn."""
        chars = tuple(PublicCharacter(c, ch.name, ch.profession) for c, ch in self.puzzle.characters.items())
        clues = [self.puzzle.clues[c] for c in self.revealed if self.puzzle.clues[c] is not None]
        return PublicState.make(self.board.size, chars, clues, self.verdicts, self.version)

    def analysis(self) -> Analysis:
        """Phân tích tính kéo theo của trạng thái công khai hiện tại (lưu cache theo version)."""
        if self._cache is None or self._cache[0] != self.version:
            self._cache = (self.version, analyze(self.public_state(), self.strategy, self.cardinality))
        return self._cache[1]

    def player_view(self) -> "PlayerView":
        """Trả về giao diện đóng gói duy nhất trao cho người chơi hoặc LogicAgent."""
        return PlayerView(self)

    # ------------------------------------------------------------ Thẩm định phán đoán
    def submit(self, cell: str, verdict: str) -> SubmitResult:
        """Kiểm tra phán đoán bằng chính KB công khai hiện tại; từ chối nếu không chứng minh được."""
        verdict = str(verdict).upper()
        if not self.board.is_cell(cell) or verdict not in (CRIMINAL_V, INNOCENT_V):
            return SubmitResult(INVALID, str(cell), verdict, "Unknown cell or verdict.")
        if self.lost is not None:
            return SubmitResult(GAME_OVER, cell, verdict, "The game is over. Restart the case to play again.")
        if cell in self.verdicts:
            return SubmitResult(ALREADY_KNOWN, cell, verdict, "This character is already solved.")

        analysis = self.analysis()
        if self._charged != self.version:
            # Mỗi phiên bản KB chỉ cộng dồn chi phí thẩm định SAT đúng một lần
            self.sat_calls += analysis.sat_calls
            self._charged = self.version

        if not analysis.consistent:
            return SubmitResult(INCONSISTENT, cell, verdict, "The public clues contradict each other.")

        forced = analysis.classification[cell]
        name = self.puzzle.characters[cell].name
        if forced == verdict:
            if self.puzzle.solution[cell] != (verdict == CRIMINAL_V):
                raise PuzzleIntegrityError(f"{cell}: entailed verdict {verdict} contradicts the stored solution")
            self.verdicts[cell] = verdict == CRIMINAL_V
            self.revealed.append(cell)
            self.version += 1
            return SubmitResult(ACCEPTED, cell, verdict, f"Correct: {name} is {verdict.lower()}.",
                                self.puzzle.clues[cell])

        if forced in (CRIMINAL_V, INNOCENT_V):
            # Giữ nguyên cơ sở tri thức (không lộ thẻ hay manh mối ẩn); ở chế độ sudden death,
            # Engine ngừng nhận phán đoán mới cho đến khi trò chơi được Restart.
            if self.sudden_death:
                self.lost = (cell, verdict)
            return SubmitResult(CONTRADICTED, cell, verdict,
                                f"Contradicted: the clues prove {name} is {forced.lower()}.")
        return SubmitResult(NOT_PROVABLE, cell, verdict,
                            f"Not provable yet: {name} could still be either. No guessing!")

    def invalidate(self) -> None:
        """Xóa cache phân tích (ví dụ sau khi người dùng đổi chiến lược hoặc cách mã hóa đếm)."""
        self._cache = None
        self._charged = None

    def uniqueness(self, time_limit: Optional[float] = None) -> UniquenessResult:
        """Kiểm tra tính duy nhất của nghiệm dựa trên toàn bộ tập manh mối (kể cả thẻ úp)."""
        clues = [c for c in self.puzzle.clues.values() if c is not None]
        initial = {c: self.puzzle.solution[c] for c in self.puzzle.initial}
        return check_uniqueness(self.board, clues, initial, limit=2, cardinality=self.cardinality,
                                time_limit=time_limit)


class PlayerView:
    """Lớp vỏ bọc trao cho LogicAgent: chỉ cung cấp đúng ``public_state()`` và ``submit()``.

    Tham chiếu tới Engine được che bằng name-mangling (``__engine``) để tác tử không thể
    vô tình truy cập trực tiếp vào ``puzzle.solution`` hoặc manh mối ẩn.
    """

    __slots__ = ("__engine",)

    def __init__(self, engine: GameEngine):
        self.__engine = engine

    def public_state(self) -> PublicState:
        return self.__engine.public_state()

    def submit(self, cell: str, verdict: str) -> SubmitResult:
        return self.__engine.submit(cell, verdict)
