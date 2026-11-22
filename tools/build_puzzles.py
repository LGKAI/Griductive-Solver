"""Sinh lại toàn bộ bộ câu đố mẫu trong thư mục ``puzzles/`` (dùng seed cố định).

    python tools/build_puzzles.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from griductive.generator import generate  # noqa: E402
from griductive.puzzle import Puzzle  # noqa: E402

OUT = ROOT / "puzzles"

SPECS = [
    # (file id, size, seed, min_waves)
    ("01-3x3-a", 3, 301, 3),
    ("02-3x3-b", 3, 302, 3),
    ("03-3x3-c", 3, 303, 4),
    ("04-3x3-d", 3, 304, 4),
    ("05-4x4-a", 4, 401, 5),
    ("06-4x4-b", 4, 402, 5),
    ("07-4x4-c", 4, 403, 6),
    ("08-4x4-d", 4, 404, 6),
    ("09-5x5-a", 5, 501, 6),
    ("10-5x5-b", 5, 502, 7),
]


def _character(cell, name, profession, status, clue):
    return {"cell": cell, "name": name, "profession": profession, "status": status, "clue": clue}


def ambiguous_case() -> Puzzle:
    """Valid clues, but two solutions: the agent must stop with STUCK, not guess."""
    c, i = "criminal", "innocent"
    row1 = {"kind": "row", "index": 1}
    data = {
        "id": "90-3x3-ambiguous", "title": "Failure case: the Twin Alibi", "size": 3, "initial": ["B2"],
        "meta": {"expected": "STUCK", "note": "Clues admit several solutions; no forced verdict exists."},
        "characters": [
            _character("A1", "Alma", "Baker", c, {"type": "DIFFERENT", "a": "A1", "b": "C1"}),
            _character("B1", "Basil", "Guard", i, {"type": "AT_LEAST", "k": 1, "region": {"kind": "corners"}}),
            _character("C1", "Cleo", "Judge", i, {"type": "SAME", "a": "C1", "b": "A3"}),
            _character("A2", "Dara", "Pilot", i, {"type": "EXACTLY", "k": 1, "region": {"kind": "col", "index": "A"}}),
            _character("B2", "Edda", "Clerk", i, {"type": "EXACTLY", "k": 1, "region": row1}),
            _character("C2", "Felix", "Chef", c, {"type": "AT_MOST", "k": 2, "region": {"kind": "row", "index": 2}}),
            _character("A3", "Greta", "Miner", i, {"type": "EXACTLY", "k": 0, "region": {"kind": "col", "index": "B"}}),
            _character("B3", "Hugo", "Tailor", i, {"type": "FACT", "cell": "C3", "status": c}),
            _character("C3", "Ines", "Writer", c, {"type": "AT_LEAST", "k": 1, "region": {"kind": "edge"}}),
        ],
    }
    return Puzzle.from_dict(data)


def inconsistent_case() -> Puzzle:
    """A deliberately broken file: the second revealed clue contradicts the first."""
    c, i = "criminal", "innocent"
    data = {
        "id": "91-3x3-inconsistent", "title": "Failure case: the Forged Testimony", "size": 3, "initial": ["B2"],
        "meta": {"expected": "INCONSISTENT", "allow_false_clues": True,
                 "note": "Deliberately broken file: some clues contradict each other. Watch the agent report INCONSISTENT instead of guessing."},
        "characters": [
            _character("A1", "Ada", "Florist", i, {"type": "FACT", "cell": "B1", "status": c}),
            _character("B1", "Bruno", "Sailor", i, {"type": "SAME", "a": "B1", "b": "C1"}),
            _character("C1", "Cyrus", "Doctor", i, {"type": "AT_MOST", "k": 1, "region": {"kind": "all"}}),
            _character("A2", "Dmitri", "Banker", c, {"type": "FACT", "cell": "A3", "status": c}),
            _character("B2", "Elio", "Coder", i, {"type": "EXACTLY", "k": 0, "region": {"kind": "row", "index": 1}}),
            _character("C2", "Faye", "Singer", c, None),
            _character("A3", "Gus", "Butler", c, None),
            _character("B3", "Hana", "Painter", i, None),
            _character("C3", "Ivo", "Farmer", i, None),
        ],
    }
    return Puzzle.from_dict(data)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    for file_id, size, seed, min_waves in SPECS:
        puzzle = generate(size, seed=seed, min_waves=min_waves, puzzle_id=file_id)
        puzzle.save(OUT / f"{file_id}.json")
        types = sorted({c.type for c in puzzle.clues.values() if c})
        print(f"{file_id}: {puzzle.title!r} waves={puzzle.meta['waves']} types={types}")
    for puzzle in (ambiguous_case(), inconsistent_case()):
        puzzle.save(OUT / f"{puzzle.puzzle_id}.json")
        print(f"{puzzle.puzzle_id}: {puzzle.title!r}")


if __name__ == "__main__":
    main()
