"""Định dạng tệp câu đố (JSON): kiểm tra cấu trúc, đọc/ghi và đối chiếu đáp án.

Cấu trúc JSON::

    {
      "id": "demo-3x3", "title": "First Case", "size": 3,
      "initial": ["B2"],
      "characters": [
        {"cell": "A1", "name": "Abel", "profession": "Cook",
         "status": "criminal", "clue": {"type": "SAME", "a": "A1", "b": "C3"}},
        ...
      ]
    }

``status`` là đáp án ẩn; chỉ GameEngine đọc trường này để kiểm tra an toàn và lật thẻ.
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

# Bảng quy đổi các ký tự đặc biệt thành ASCII để xếp thứ tự bảng chữ cái chuẩn xác
_FOLD = str.maketrans({"Ø": "O", "ø": "o", "Đ": "D", "đ": "d", "Ł": "L", "ł": "l", "Æ": "AE", "æ": "ae",
                       "Œ": "OE", "œ": "oe", "ß": "ss"})


def name_key(name: str) -> str:
    """Khóa sắp xếp tên theo bảng chữ cái không phân biệt dấu (ví dụ Ødegaard ~ Odegaard, Văn ~ Van)."""
    decomposed = unicodedata.normalize("NFKD", name.translate(_FOLD))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


class PuzzleError(ValueError):
    """Ngoại lệ khi tệp câu đố JSON bị lỗi cấu trúc hoặc vi phạm ràng buộc hợp lệ."""


@dataclass(frozen=True)
class Character:
    """Thông tin một nhân vật gắn với ô trên bàn cờ."""

    cell: str
    name: str
    profession: str
    # Đặc tả ảnh/avatar hiển thị từ themes.py; None nghĩa là dùng avatar mặc định theo tên
    avatar: Optional[dict] = field(default=None, compare=False)


@dataclass
class Puzzle:
    """Biểu diễn đầy đủ một ván câu đố Griductive."""

    puzzle_id: str
    title: str
    board: Board
    characters: dict[str, Character]
    solution: dict[str, bool]         # cell -> True nếu là criminal (dữ liệu ẩn)
    clues: dict[str, Optional[Clue]]  # cell -> manh mối sẽ mở khi thẻ được lật
    initial: tuple[str, ...]
    meta: dict = field(default_factory=dict)

    # --------------------------------------------------------------- Đọc / Ghi JSON
    @classmethod
    def from_dict(cls, data: dict) -> "Puzzle":
        """Phân tích và kiểm tra toàn diện dữ liệu câu đố từ dictionary."""
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

        # Luật chơi: tên nhân vật phải xếp theo thứ tự bảng chữ cái theo hàng (trừ tệp không đặt tên riêng)
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
        # Cờ ``allow_false_clues`` chỉ dùng cho các ca test cố tình mâu thuẫn (ví dụ ca lỗi 91)
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

    # ---------------------------------------------------------- Kiểm tra đối chứng
    def false_clues(self) -> list[str]:
        """Danh sách ô có manh mối sai trên chính đáp án lưu trong tệp (bình thường phải rỗng)."""
        return [c for c, clue in self.clues.items() if clue is not None and not evaluate(clue, self.solution)]

    def brute_force_solutions(self, limit: int = 2) -> list[dict[str, bool]]:
        """Bộ đếm nghiệm tham chiếu bằng vét cạn (chỉ dùng cho lưới <= 4x4 trong unit test)."""
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
