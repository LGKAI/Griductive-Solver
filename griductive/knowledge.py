"""Quản lý trạng thái tri thức công khai và dựng Cơ sở tri thức (Knowledge Base).

``PublicState`` là đối tượng duy nhất mà Logic Agent được phép đọc: chỉ chứa
hình học lưới, tên/nghề nhân vật, các manh mối đã lật và phán đoán đã chứng minh.
Tuyệt đối không chứa đáp án ẩn hoặc manh mối chưa mở:

    KB_t = CNF(các manh mối đã lật)  AND  mệnh đề đơn vị cho các ô đã chứng minh
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable, Mapping

from .board import Board
from .clues import CRIMINAL, INNOCENT, Clue
from .cnf import CNF, ClueEncoder, VarMap


@dataclass(frozen=True)
class PublicCharacter:
    """Thông tin công khai của một nhân vật trên giao diện và PublicState."""

    cell: str
    name: str
    profession: str


@dataclass(frozen=True)
class PublicState:
    """Ảnh chụp bất biến của tri thức công khai tại bước hiện tại."""

    size: int
    characters: tuple[PublicCharacter, ...]
    revealed_clues: tuple[Clue, ...]  # Xếp theo thứ tự row-major của chủ thẻ
    verdicts: Mapping[str, bool]      # Các ô đã chứng minh: cell -> True nếu là criminal
    version: int = 0

    @property
    def board(self) -> Board:
        return Board(self.size)

    @property
    def unknown_cells(self) -> tuple[str, ...]:
        """Danh sách các ô chưa được chứng minh theo thứ tự row-major."""
        return tuple(c for c in self.board.cells if c not in self.verdicts)

    @property
    def active_clue_ids(self) -> tuple[str, ...]:
        return tuple(c.clue_id for c in self.revealed_clues)

    def name(self, cell: str) -> str:
        for ch in self.characters:
            if ch.cell == cell:
                return ch.name
        return cell

    @staticmethod
    def make(size: int, characters: Iterable[PublicCharacter], clues: Iterable[Clue],
             verdicts: Mapping[str, bool], version: int = 0) -> "PublicState":
        board = Board(size)
        ordered = tuple(sorted(clues, key=lambda c: board.index(c.clue_id) if board.is_cell(c.clue_id) else -1))
        return PublicState(size, tuple(characters), ordered, MappingProxyType(dict(verdicts)), version)


@dataclass
class KnowledgeBase:
    """Cơ sở tri thức đã mã hóa sang CNF kèm ánh xạ biến và khoảng chỉ mục mệnh đề của từng manh mối."""

    varmap: VarMap
    cnf: CNF
    clue_clauses: dict[str, tuple[int, int]] = field(default_factory=dict)  # clue_id -> [start, end)

    @property
    def stats(self) -> dict:
        return {
            "primary_vars": self.cnf.num_primary,
            "aux_vars": self.cnf.num_aux,
            "clauses": len(self.cnf.clauses),
        }


def build_kb(board: Board, clues: Iterable[Clue], verdicts: Mapping[str, bool],
             cardinality: str = "auto") -> KnowledgeBase:
    """Mã hóa tập manh mối và phán đoán thành KnowledgeBase theo thứ tự tất định."""
    varmap = VarMap(board)
    cnf = CNF(num_primary=varmap.num_primary)
    encoder = ClueEncoder(varmap, cardinality)
    kb = KnowledgeBase(varmap, cnf)
    for clue in clues:
        start = len(cnf.clauses)
        cnf.set_tag(clue.clue_id)
        encoder.encode(cnf, clue)
        kb.clue_clauses[clue.clue_id] = (start, len(cnf.clauses))
    for cell in board.cells:
        if cell in verdicts:
            cnf.set_tag(f"verdict:{cell}")
            cnf.add([varmap.literal(cell, CRIMINAL if verdicts[cell] else INNOCENT)])
    cnf.set_tag("")
    return kb


def build_public_kb(state: PublicState, cardinality: str = "auto") -> KnowledgeBase:
    """Dựng cơ sở tri thức KB_t chỉ từ trạng thái công khai PublicState."""
    return build_kb(state.board, state.revealed_clues, state.verdicts, cardinality)
