"""Board geometry and region resolution.

Cells are identified by strings such as ``"C2"`` (column letter, row number).
Rows are numbered from 1 (top) and columns are lettered from ``A`` (left).
The canonical cell order is row-major: A1, B1, C1, ..., A2, B2, ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

COLUMN_LETTERS = "ABCDEFGHIJ"
_CELL_RE = re.compile(r"([A-J])([1-9][0-9]?)")  # always used with fullmatch

DIRECTIONS = {
    "left": (-1, 0),
    "right": (1, 0),
    "above": (0, -1),
    "below": (0, 1),
}


class RegionError(ValueError):
    """Raised when a region specification is malformed or out of bounds."""


@dataclass(frozen=True)
class Board:
    """An ``size x size`` grid. Holds geometry only, never statuses."""

    size: int

    def __post_init__(self) -> None:
        if not 2 <= self.size <= len(COLUMN_LETTERS):
            raise ValueError(f"board size must be between 2 and {len(COLUMN_LETTERS)}")

    # ------------------------------------------------------------------ cells
    @property
    def cells(self) -> tuple[str, ...]:
        return tuple(self.cell_id(c, r) for r in range(self.size) for c in range(self.size))

    def cell_id(self, col: int, row: int) -> str:
        """Zero-based (col, row) -> identifier such as ``"B3"``."""
        return f"{COLUMN_LETTERS[col]}{row + 1}"

    def coords(self, cell: str) -> tuple[int, int]:
        """Identifier -> zero-based (col, row). Raises RegionError if invalid."""
        match = _CELL_RE.fullmatch(cell) if isinstance(cell, str) else None
        if not match:
            raise RegionError(f"invalid cell identifier {cell!r}")
        col = COLUMN_LETTERS.index(match.group(1))
        row = int(match.group(2)) - 1
        if not (0 <= col < self.size and 0 <= row < self.size):
            raise RegionError(f"cell {cell} is outside the {self.size}x{self.size} board")
        return col, row

    def is_cell(self, cell: object) -> bool:
        try:
            self.coords(cell)  # type: ignore[arg-type]
        except RegionError:
            return False
        return True

    def index(self, cell: str) -> int:
        """Row-major index of a cell (0-based)."""
        col, row = self.coords(cell)
        return row * self.size + col

    def sort_cells(self, cells: Iterable[str]) -> tuple[str, ...]:
        return tuple(sorted(set(cells), key=self.index))

    # ------------------------------------------------------- basic regions
    def row(self, number: int) -> tuple[str, ...]:
        if not isinstance(number, int) or isinstance(number, bool) or not 1 <= number <= self.size:
            raise RegionError(f"row {number!r} does not exist")
        return tuple(self.cell_id(c, number - 1) for c in range(self.size))

    def column(self, letter: str) -> tuple[str, ...]:
        if not isinstance(letter, str) or letter not in COLUMN_LETTERS[: self.size] or len(letter) != 1:
            raise RegionError(f"column {letter!r} does not exist")
        col = COLUMN_LETTERS.index(letter)
        return tuple(self.cell_id(col, r) for r in range(self.size))

    def neighbors(self, cell: str) -> tuple[str, ...]:
        """The up-to-eight cells touching ``cell`` (the cell itself excluded)."""
        col, row = self.coords(cell)
        out = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                c, r = col + dc, row + dr
                if 0 <= c < self.size and 0 <= r < self.size:
                    out.append(self.cell_id(c, r))
        return self.sort_cells(out)

    def corners(self) -> tuple[str, ...]:
        n = self.size - 1
        return self.sort_cells([self.cell_id(0, 0), self.cell_id(n, 0), self.cell_id(0, n), self.cell_id(n, n)])

    def edge(self) -> tuple[str, ...]:
        n = self.size - 1
        return tuple(c for c in self.cells if 0 in self.coords(c) or n in self.coords(c))

    def ray(self, cell: str, direction: str) -> tuple[str, ...]:
        """All cells strictly to the left/right/above/below ``cell``."""
        if not isinstance(direction, str) or direction not in DIRECTIONS:
            raise RegionError(f"unknown direction {direction!r}")
        dc, dr = DIRECTIONS[direction]
        col, row = self.coords(cell)
        out = []
        col, row = col + dc, row + dr
        while 0 <= col < self.size and 0 <= row < self.size:
            out.append(self.cell_id(col, row))
            col, row = col + dc, row + dr
        return self.sort_cells(out)

    def between(self, a: str, b: str) -> tuple[str, ...]:
        """Cells strictly between two cells sharing a row or a column."""
        (ca, ra), (cb, rb) = self.coords(a), self.coords(b)
        if a == b:
            raise RegionError("'between' needs two different cells")
        if ra == rb:
            lo, hi = sorted((ca, cb))
            return tuple(self.cell_id(c, ra) for c in range(lo + 1, hi))
        if ca == cb:
            lo, hi = sorted((ra, rb))
            return tuple(self.cell_id(ca, r) for r in range(lo + 1, hi))
        raise RegionError(f"{a} and {b} are not in the same row or column")

    def is_line_segment(self, cells: Iterable[str]) -> bool:
        """True if the cells form one contiguous horizontal or vertical segment."""
        coords = sorted(self.coords(c) for c in cells)
        if len(coords) <= 1:
            return True
        cols = {c for c, _ in coords}
        rows = {r for _, r in coords}
        if len(rows) == 1:
            xs = sorted(cols)
            return xs == list(range(xs[0], xs[0] + len(xs)))
        if len(cols) == 1:
            ys = sorted(rows)
            return ys == list(range(ys[0], ys[0] + len(ys)))
        return False


# ---------------------------------------------------------------- regions
CORE_REGION_KINDS = ("row", "col", "neighbors", "cells")
EXTENDED_REGION_KINDS = (
    "all", "corners", "edge", "ray", "between", "common_neighbors", "intersect", "union", "minus",
)
REGION_KINDS = CORE_REGION_KINDS + EXTENDED_REGION_KINDS


def _require(spec: dict, *keys: str) -> None:
    missing = [k for k in keys if k not in spec]
    if missing:
        raise RegionError(f"region {spec.get('kind')!r} is missing field(s): {', '.join(missing)}")


def resolve_region(board: Board, spec: dict) -> tuple[str, ...]:
    """Like :func:`_resolve_region`, but malformed values (e.g. a list where a
    string is expected) always surface as :class:`RegionError`."""
    try:
        return _resolve_region(board, spec)
    except (TypeError, AttributeError) as exc:
        raise RegionError(f"malformed region {spec!r}: {exc}") from None


def _resolve_region(board: Board, spec: dict) -> tuple[str, ...]:
    """Resolve a structured region specification into an ordered tuple of cells.

    Core kinds (required by the assignment)::

        {"kind": "row", "index": 2}
        {"kind": "col", "index": "B"}
        {"kind": "neighbors", "of": "B2"}
        {"kind": "cells", "cells": ["A1", "C3"]}

    Extended kinds (advanced region expressions)::

        {"kind": "all"} | {"kind": "corners"} | {"kind": "edge"}
        {"kind": "ray", "of": "B2", "dir": "left|right|above|below"}
        {"kind": "between", "a": "A1", "b": "D1"}
        {"kind": "common_neighbors", "a": "A1", "b": "C1"}
        {"kind": "intersect", "regions": [r1, r2, ...]}
        {"kind": "union", "regions": [r1, r2, ...]}
        {"kind": "minus", "base": r1, "remove": r2}
    """
    if not isinstance(spec, dict) or "kind" not in spec:
        raise RegionError(f"region must be an object with a 'kind' field, got {spec!r}")
    kind = spec["kind"]
    if kind == "row":
        _require(spec, "index")
        return board.row(spec["index"])
    if kind == "col":
        _require(spec, "index")
        return board.column(spec["index"])
    if kind == "neighbors":
        _require(spec, "of")
        return board.neighbors(spec["of"])
    if kind == "cells":
        _require(spec, "cells")
        cells = spec["cells"]
        if not isinstance(cells, list) or not cells:
            raise RegionError("'cells' must be a non-empty list")
        for c in cells:
            board.coords(c)
        if len(set(cells)) != len(cells):
            raise RegionError("explicit region lists a cell more than once")
        return board.sort_cells(cells)
    if kind == "all":
        return board.cells
    if kind == "corners":
        return board.corners()
    if kind == "edge":
        return board.edge()
    if kind == "ray":
        _require(spec, "of", "dir")
        return board.ray(spec["of"], spec["dir"])
    if kind == "between":
        _require(spec, "a", "b")
        return board.between(spec["a"], spec["b"])
    if kind == "common_neighbors":
        _require(spec, "a", "b")
        if spec["a"] == spec["b"]:
            raise RegionError("'common_neighbors' needs two different cells")
        common = set(board.neighbors(spec["a"])) & set(board.neighbors(spec["b"]))
        return board.sort_cells(common)
    if kind in ("intersect", "union"):
        _require(spec, "regions")
        parts = spec["regions"]
        if not isinstance(parts, list) or len(parts) < 2:
            raise RegionError(f"'{kind}' needs a list of at least two regions")
        sets = [set(resolve_region(board, p)) for p in parts]
        combined = set.intersection(*sets) if kind == "intersect" else set.union(*sets)
        return board.sort_cells(combined)
    if kind == "minus":
        _require(spec, "base", "remove")
        base = resolve_region(board, spec["base"])
        removed = set(resolve_region(board, spec["remove"]))
        return tuple(c for c in base if c not in removed)
    raise RegionError(f"unknown region kind {kind!r}")


def region_anchor_cells(spec: dict) -> list[str]:
    """Cells *named* by a region spec (e.g. the centre of 'neighbors'), for highlighting."""
    if not isinstance(spec, dict):
        return []
    kind = spec.get("kind")
    out: list[str] = []
    if kind in ("neighbors", "ray"):
        out.append(spec.get("of"))
    elif kind in ("between", "common_neighbors"):
        out.extend([spec.get("a"), spec.get("b")])
    elif kind in ("intersect", "union"):
        for part in spec.get("regions", []):
            out.extend(region_anchor_cells(part))
    elif kind == "minus":
        out.extend(region_anchor_cells(spec.get("base", {})))
        out.extend(region_anchor_cells(spec.get("remove", {})))
    return [c for c in out if isinstance(c, str)]


def describe_region(spec: dict) -> str:
    """Human-readable description. Cell references appear as ``{B2}`` tokens."""
    kind = spec.get("kind")
    if kind == "row":
        return f"row {spec['index']}"
    if kind == "col":
        return f"column {spec['index']}"
    if kind == "neighbors":
        return f"{{{spec['of']}}}'s neighbors"
    if kind == "cells":
        cells = [f"{{{c}}}" for c in spec["cells"]]
        return _join(cells)
    if kind == "all":
        return "the whole board"
    if kind == "corners":
        return "the corners"
    if kind == "edge":
        return "the edge of the board"
    if kind == "ray":
        word = {"left": "to the left of", "right": "to the right of", "above": "above", "below": "below"}[spec["dir"]]
        return f"everyone {word} {{{spec['of']}}}"
    if kind == "between":
        return f"everyone between {{{spec['a']}}} and {{{spec['b']}}}"
    if kind == "common_neighbors":
        return f"the common neighbors of {{{spec['a']}}} and {{{spec['b']}}}"
    if kind == "intersect":
        return " who are also in ".join(describe_region(p) for p in spec["regions"])
    if kind == "union":
        return " or ".join(describe_region(p) for p in spec["regions"])
    if kind == "minus":
        return f"{describe_region(spec['base'])} except {describe_region(spec['remove'])}"
    return str(spec)


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f" and {items[-1]}"
