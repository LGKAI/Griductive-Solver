"""Structured clue language: validation, direct semantic evaluation and rendering.

A clue is a small JSON-like object. Six core templates are required by the
assignment; four extension templates are provided on top of them.

Core::

    {"type": "FACT",      "cell": "B2", "status": "criminal"}
    {"type": "SAME",      "a": "A1", "b": "C3"}
    {"type": "DIFFERENT", "a": "A1", "b": "C3"}
    {"type": "EXACTLY",   "k": 2, "region": {...}, "who": "criminal"}
    {"type": "AT_LEAST",  "k": 1, "region": {...}, "who": "criminal"}
    {"type": "AT_MOST",   "k": 1, "region": {...}, "who": "criminal"}

``who`` is optional (default ``"criminal"``); ``"innocent"`` counts innocents.

Extensions::

    {"type": "PARITY",    "parity": "odd|even", "region": {...}, "who": ...}
    {"type": "COMPARE",   "op": "more|fewer|equal", "left": {...}, "right": {...}, "who": ...}
    {"type": "CONNECTED", "region": {...}, "who": ...}
    {"type": "IMPLIES",   "if": {"cell": "A1", "status": "criminal"},
                          "then": {"cell": "B2", "status": "innocent"}}

Regions additionally support the advanced expressions listed in
:func:`griductive.board.resolve_region`.

``evaluate`` decides truth directly on a complete assignment and never calls
the CNF encoder, so it can be used to cross-check the encoder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .board import Board, RegionError, describe_region, region_anchor_cells, resolve_region

CRIMINAL = "criminal"
INNOCENT = "innocent"
STATUSES = (CRIMINAL, INNOCENT)

CORE_TYPES = ("FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST")
EXTENSION_TYPES = ("PARITY", "COMPARE", "CONNECTED", "IMPLIES")
CLUE_TYPES = CORE_TYPES + EXTENSION_TYPES
COUNTING_TYPES = ("EXACTLY", "AT_LEAST", "AT_MOST")


class ClueError(ValueError):
    """Raised when a clue is malformed or refers to cells that do not exist."""


@dataclass(frozen=True)
class Clue:
    """A validated clue. ``clue_id`` is normally the owner's cell id."""

    clue_id: str
    type: str
    params: Mapping = field(hash=False, compare=False)
    raw: Mapping = field(hash=False, compare=False, repr=False)

    def to_dict(self) -> dict:
        return dict(self.raw)


# ---------------------------------------------------------------- parsing
def _status(value: object, where: str) -> str:
    if value not in STATUSES:
        raise ClueError(f"{where}: status must be 'criminal' or 'innocent', got {value!r}")
    return value  # type: ignore[return-value]


def _cell(board: Board, value: object, where: str) -> str:
    try:
        board.coords(value)  # type: ignore[arg-type]
    except RegionError as exc:
        raise ClueError(f"{where}: {exc}") from None
    return value  # type: ignore[return-value]


def _region(board: Board, spec: object, where: str) -> tuple[str, ...]:
    try:
        cells = resolve_region(board, spec)  # type: ignore[arg-type]
    except RegionError as exc:
        raise ClueError(f"{where}: {exc}") from None
    if not cells:
        raise ClueError(f"{where}: region is empty")
    return cells


def _int(value: object, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ClueError(f"{where}: k must be an integer, got {value!r}")
    return value


def parse_clue(board: Board, data: Mapping, clue_id: str = "") -> Clue:
    """Validate a clue dictionary against a board and return a :class:`Clue`.

    ``params`` holds the resolved data used by the evaluator and encoder
    (cells, resolved regions, normalised ``who``), so later stages never
    re-resolve regions.
    """
    if not isinstance(data, Mapping):
        raise ClueError(f"clue {clue_id}: must be an object")
    ctype = data.get("type")
    where = f"clue {clue_id or '?'} ({ctype})"
    if ctype not in CLUE_TYPES:
        raise ClueError(f"{where}: unknown clue type")
    p: dict = {}
    if ctype == "FACT":
        p["cell"] = _cell(board, data.get("cell"), where)
        p["status"] = _status(data.get("status"), where)
    elif ctype in ("SAME", "DIFFERENT"):
        p["a"] = _cell(board, data.get("a"), where)
        p["b"] = _cell(board, data.get("b"), where)
        if p["a"] == p["b"]:
            raise ClueError(f"{where}: needs two different people")
    elif ctype in COUNTING_TYPES:
        p["region"] = _region(board, data.get("region"), where)
        p["k"] = _int(data.get("k"), where)
        p["who"] = _status(data.get("who", CRIMINAL), where)
        if not 0 <= p["k"] <= len(p["region"]):
            raise ClueError(f"{where}: k={p['k']} must satisfy 0 <= k <= |R| = {len(p['region'])}")
    elif ctype == "PARITY":
        p["region"] = _region(board, data.get("region"), where)
        p["who"] = _status(data.get("who", CRIMINAL), where)
        if data.get("parity") not in ("odd", "even"):
            raise ClueError(f"{where}: parity must be 'odd' or 'even'")
        p["parity"] = data["parity"]
    elif ctype == "COMPARE":
        p["left"] = _region(board, data.get("left"), where + " left")
        p["right"] = _region(board, data.get("right"), where + " right")
        p["who"] = _status(data.get("who", CRIMINAL), where)
        if data.get("op") not in ("more", "fewer", "equal"):
            raise ClueError(f"{where}: op must be 'more', 'fewer' or 'equal'")
        p["op"] = data["op"]
    elif ctype == "CONNECTED":
        p["region"] = _region(board, data.get("region"), where)
        p["who"] = _status(data.get("who", CRIMINAL), where)
        if not board.is_line_segment(p["region"]):
            raise ClueError(f"{where}: CONNECTED needs a contiguous row/column segment")
    elif ctype == "IMPLIES":
        for part in ("if", "then"):
            sub = data.get(part)
            if not isinstance(sub, Mapping):
                raise ClueError(f"{where}: '{part}' must be an object with cell and status")
            p[part] = (_cell(board, sub.get("cell"), where), _status(sub.get("status"), where))
        if p["if"][0] == p["then"][0]:
            raise ClueError(f"{where}: 'if' and 'then' must name different people")
    return Clue(clue_id=clue_id, type=ctype, params=p, raw=dict(data))


# ------------------------------------------------------ semantic evaluator
def _count(cells, assignment: Mapping[str, bool], who: str) -> int:
    want = who == CRIMINAL
    return sum(1 for c in cells if assignment[c] == want)


def evaluate(clue: Clue, assignment: Mapping[str, bool]) -> bool:
    """Truth of ``clue`` under a complete assignment ``cell -> is_criminal``.

    Implemented directly from the clue's meaning, independent of CNF.
    """
    p = clue.params
    t = clue.type
    if t == "FACT":
        return assignment[p["cell"]] == (p["status"] == CRIMINAL)
    if t == "SAME":
        return assignment[p["a"]] == assignment[p["b"]]
    if t == "DIFFERENT":
        return assignment[p["a"]] != assignment[p["b"]]
    if t == "EXACTLY":
        return _count(p["region"], assignment, p["who"]) == p["k"]
    if t == "AT_LEAST":
        return _count(p["region"], assignment, p["who"]) >= p["k"]
    if t == "AT_MOST":
        return _count(p["region"], assignment, p["who"]) <= p["k"]
    if t == "PARITY":
        n = _count(p["region"], assignment, p["who"])
        return (n % 2 == 1) == (p["parity"] == "odd")
    if t == "COMPARE":
        left = _count(p["left"], assignment, p["who"])
        right = _count(p["right"], assignment, p["who"])
        return {"more": left > right, "fewer": left < right, "equal": left == right}[p["op"]]
    if t == "CONNECTED":
        want = p["who"] == CRIMINAL
        positions = [i for i, c in enumerate(p["region"]) if assignment[c] == want]
        return not positions or positions[-1] - positions[0] + 1 == len(positions)
    if t == "IMPLIES":
        (ca, sa), (cb, sb) = p["if"], p["then"]
        premise = assignment[ca] == (sa == CRIMINAL)
        conclusion = assignment[cb] == (sb == CRIMINAL)
        return (not premise) or conclusion
    raise ClueError(f"cannot evaluate clue type {t}")


# --------------------------------------------------------------- display
def _plural(who: str, k: int) -> str:
    word = "criminal" if who == CRIMINAL else "innocent"
    return word if k == 1 else word + "s"


def clue_text(clue: Clue) -> str:
    """English rendering; people appear as ``{B2}`` tokens for the GUI to fill in."""
    r = clue.raw
    t = clue.type
    if t == "FACT":
        return f"{{{r['cell']}}} is {'a criminal' if r['status'] == CRIMINAL else 'innocent'}"
    if t == "SAME":
        return f"{{{r['a']}}} and {{{r['b']}}} have the same status"
    if t == "DIFFERENT":
        return f"{{{r['a']}}} and {{{r['b']}}} have different statuses"
    who = r.get("who", CRIMINAL)
    if t in COUNTING_TYPES:
        k = r["k"]
        region = describe_region(r["region"])
        if k == 0 and t != "AT_LEAST":
            return f"There are no {_plural(who, 2)} in {region}"
        word = {"EXACTLY": "Exactly", "AT_LEAST": "At least", "AT_MOST": "At most"}[t]
        return f"{word} {k} {_plural(who, k)} in {region}"
    if t == "PARITY":
        return f"There is an {r['parity']} number of {_plural(who, 2)} in {describe_region(r['region'])}"
    if t == "COMPARE":
        left, right = describe_region(r["left"]), describe_region(r["right"])
        if r["op"] == "equal":
            return f"There are as many {_plural(who, 2)} in {left} as in {right}"
        word = "more" if r["op"] == "more" else "fewer"
        return f"There are {word} {_plural(who, 2)} in {left} than in {right}"
    if t == "CONNECTED":
        return f"All {_plural(who, 2)} in {describe_region(r['region'])} are connected"
    if t == "IMPLIES":
        a, b = r["if"], r["then"]
        sa = "a criminal" if a["status"] == CRIMINAL else "innocent"
        sb = "a criminal" if b["status"] == CRIMINAL else "innocent"
        return f"If {{{a['cell']}}} is {sa}, then {{{b['cell']}}} is {sb}"
    return t


def clue_references(clue: Clue) -> dict[str, list[str]]:
    """Cells to highlight: ``counted`` (inside counted regions) and ``named`` people."""
    p, r, t = clue.params, clue.raw, clue.type
    counted: list[str] = []
    named: list[str] = []
    if t == "FACT":
        named = [p["cell"]]
    elif t in ("SAME", "DIFFERENT"):
        named = [p["a"], p["b"]]
    elif t in COUNTING_TYPES or t in ("PARITY", "CONNECTED"):
        counted = list(p["region"])
        named = region_anchor_cells(r["region"])
    elif t == "COMPARE":
        counted = list(dict.fromkeys(list(p["left"]) + list(p["right"])))
        named = region_anchor_cells(r["left"]) + region_anchor_cells(r["right"])
    elif t == "IMPLIES":
        named = [p["if"][0], p["then"][0]]
    return {"counted": counted, "named": list(dict.fromkeys(named))}
