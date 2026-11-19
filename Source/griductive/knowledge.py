"""Public knowledge state and knowledge-base construction.

``PublicState`` is the only thing the Logic Agent ever sees: the board
geometry, character names, revealed clues and proved verdicts. It never
contains hidden statuses or unrevealed clues.

    KB_t = CNF(revealed clues)  AND  unit clauses for proved verdicts
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
    cell: str
    name: str
    profession: str


@dataclass(frozen=True)
class PublicState:
    size: int
    characters: tuple[PublicCharacter, ...]
    revealed_clues: tuple[Clue, ...]  # in row-major order of their owners
    verdicts: Mapping[str, bool]  # proved statuses: cell -> is criminal
    version: int = 0

    @property
    def board(self) -> Board:
        return Board(self.size)

    @property
    def unknown_cells(self) -> tuple[str, ...]:
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
    varmap: VarMap
    cnf: CNF
    clue_clauses: dict[str, tuple[int, int]] = field(default_factory=dict)  # clue id -> [start, end)

    @property
    def stats(self) -> dict:
        return {
            "primary_vars": self.cnf.num_primary,
            "aux_vars": self.cnf.num_aux,
            "clauses": len(self.cnf.clauses),
        }


def build_kb(board: Board, clues: Iterable[Clue], verdicts: Mapping[str, bool],
             cardinality: str = "auto") -> KnowledgeBase:
    """Encode the given clues and verdicts. Clue order is preserved (deterministic)."""
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
    return build_kb(state.board, state.revealed_clues, state.verdicts, cardinality)
