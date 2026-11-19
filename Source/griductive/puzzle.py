"""Puzzle files: characters, hidden solution, clues and the initial face-up cards.

JSON format::

    {
      "id": "demo-3x3", "title": "First Case", "size": 3,
      "initial": ["B2"],
      "characters": [
        {"cell": "A1", "name": "Abel", "profession": "Cook",
         "status": "criminal", "clue": {"type": "SAME", "a": "A1", "b": "C3"}},
        ...
      ]
    }

``status`` is the hidden solution. Only the Game Engine reads it.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Optional

from .board import Board
from .clues import CRIMINAL, INNOCENT, Clue, ClueError, evaluate, parse_clue


_FOLD = str.maketrans({"Ø": "O", "ø": "o", "Đ": "D", "đ": "d", "Ł": "L", "ł": "l", "Æ": "AE", "æ": "ae",
                       "Œ": "OE", "œ": "oe", "ß": "ss"})


def name_key(name: str) -> str:
    """Alphabetical sort key for display names: accents are ignored (Ødegaard ~ Odegaard, Văn ~ Van)."""
    decomposed = unicodedata.normalize("NFKD", name.translate(_FOLD))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


class PuzzleError(ValueError):
    """Raised for malformed puzzle files."""


@dataclass(frozen=True)
class Character:
    cell: str
    name: str
    profession: str
    # Cosmetic portrait spec set by a character theme (see themes.py); None = default portrait.
    avatar: Optional[dict] = field(default=None, compare=False)


@dataclass
class Puzzle:
    puzzle_id: str
    title: str
    board: Board
    characters: dict[str, Character]
    solution: dict[str, bool]  # cell -> is criminal (hidden)
    clues: dict[str, Optional[Clue]]  # cell -> clue revealed when the card flips
    initial: tuple[str, ...]
    meta: dict = field(default_factory=dict)

    # --------------------------------------------------------------- I/O
    @classmethod
    def from_dict(cls, data: dict) -> "Puzzle":
        if not isinstance(data, dict):
            raise PuzzleError("puzzle must be a JSON object")
        size = data.get("size")
        if type(size) is not int:
            raise PuzzleError("'size' must be an integer")
        try:
            board = Board(size)
        except ValueError as exc:
            raise PuzzleError(f"invalid 'size': {exc}") from None
        if not isinstance(data.get("meta", {}), dict):
            raise PuzzleError("'meta' must be an object")
        chars_data = data.get("characters")
        if not isinstance(chars_data, list):
            raise PuzzleError("'characters' must be a list")
        characters: dict[str, Character] = {}
        solution: dict[str, bool] = {}
        raw_clues: dict[str, Optional[dict]] = {}
        for entry in chars_data:
            if not isinstance(entry, dict):
                raise PuzzleError("each character must be an object")
            cell = entry.get("cell")
            if not board.is_cell(cell):
                raise PuzzleError(f"character has invalid cell {cell!r}")
            if cell in characters:
                raise PuzzleError(f"cell {cell} is used by two characters")
            status = entry.get("status")
            if status not in (CRIMINAL, INNOCENT):
                raise PuzzleError(f"{cell}: status must be 'criminal' or 'innocent'")
            name = str(entry.get("name") or cell)
            characters[cell] = Character(cell, name, str(entry.get("profession", "")))
            solution[cell] = status == CRIMINAL
            raw_clues[cell] = entry.get("clue")
        missing = [c for c in board.cells if c not in characters]
        if missing:
            raise PuzzleError(f"no character for cell(s): {', '.join(missing)}")
        names = [characters[c].name for c in board.cells]
        if len(set(names)) != len(names):
            raise PuzzleError("character names must be unique")
        # Game rule: characters are ordered alphabetically by display name (row-major).
        # Files without names (every name defaults to its cell id) are exempt.
        if any(n != c for n, c in zip(names, board.cells)) and names != sorted(names, key=name_key):
            raise PuzzleError("characters must be ordered alphabetically by name in row-major order")
        clues: dict[str, Optional[Clue]] = {}
        for cell in board.cells:
            raw = raw_clues[cell]
            if raw is None:
                clues[cell] = None
                continue
            try:
                clues[cell] = parse_clue(board, raw, clue_id=cell)
            except ClueError as exc:
                raise PuzzleError(str(exc)) from None
        initial = data.get("initial")
        if not isinstance(initial, list) or not initial:
            raise PuzzleError("'initial' must be a non-empty list of face-up cells")
        for cell in initial:
            if not board.is_cell(cell):
                raise PuzzleError(f"initial cell {cell!r} is invalid")
        if len(set(initial)) != len(initial):
            raise PuzzleError("'initial' lists a cell twice")
        puzzle = cls(
            puzzle_id=str(data.get("id", "puzzle")),
            title=str(data.get("title", data.get("id", "Untitled case"))),
            board=board,
            characters=characters,
            solution=solution,
            clues=clues,
            initial=board.sort_cells(initial),
            meta=dict(data.get("meta", {})),
        )
        false_clues = puzzle.false_clues()
        # ``allow_false_clues`` exists only for deliberately broken test cases
        # (e.g. demonstrating INCONSISTENT detection).
        if false_clues and not puzzle.meta.get("allow_false_clues"):
            raise PuzzleError(f"clue(s) false under the stated solution: {', '.join(false_clues)}")
        return puzzle

    @classmethod
    def load(cls, path: str | Path) -> "Puzzle":
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PuzzleError(f"{path}: invalid JSON ({exc})") from None
        except UnicodeDecodeError:
            raise PuzzleError(f"{path}: the file is not UTF-8 text") from None
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        return {
            "id": self.puzzle_id,
            "title": self.title,
            "size": self.board.size,
            "initial": list(self.initial),
            "meta": self.meta,
            "characters": [
                {
                    "cell": c,
                    "name": self.characters[c].name,
                    "profession": self.characters[c].profession,
                    "status": CRIMINAL if self.solution[c] else INNOCENT,
                    "clue": self.clues[c].to_dict() if self.clues[c] else None,
                }
                for c in self.board.cells
            ],
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # ---------------------------------------------------------- checks
    def false_clues(self) -> list[str]:
        """Clue ids that are false under the stored solution (should be empty)."""
        return [c for c, clue in self.clues.items() if clue is not None and not evaluate(clue, self.solution)]

    def brute_force_solutions(self, limit: int = 2) -> list[dict[str, bool]]:
        """Reference model counter by enumeration (only for small boards / tests)."""
        cells = self.board.cells
        if len(cells) > 16:
            raise ValueError("brute force is limited to boards with at most 16 cells")
        known = {c: self.solution[c] for c in self.initial}
        active = [clue for clue in self.clues.values() if clue is not None]
        found = []
        for values in product((False, True), repeat=len(cells)):
            assignment = dict(zip(cells, values))
            if any(assignment[c] != v for c, v in known.items()):
                continue
            if all(evaluate(clue, assignment) for clue in active):
                found.append(assignment)
                if len(found) >= limit:
                    break
        return found
