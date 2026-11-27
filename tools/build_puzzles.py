"""Sinh lại toàn bộ bộ câu đố mẫu trong thư mục ``puzzles/`` (dùng seed cố định).

    python tools/build_puzzles.py

Mỗi câu đố được lưu kèm bộ cầu thủ và tiêu đề mà giao diện hiển thị (xem ``themes.py``),
nên dòng lệnh (``main.py --solve``), giao diện web và báo cáo dùng chung một bộ tên.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from griductive.generator import generate  # noqa: E402
from griductive.puzzle import Puzzle  # noqa: E402
from griductive.themes import DEFAULT_THEME, themed_characters  # noqa: E402

OUT = ROOT / "puzzles"

SPECS = [
    # (mã tệp, kích thước, seed, số đợt suy luận tối thiểu)
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
    """Câu đố hợp lệ nhưng có nhiều nghiệm: tác tử phải dừng ở STUCK và không đoán mò."""
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
    """Ca thử nghiệm cố tình mâu thuẫn: manh mối thứ hai phủ định manh mối đầu tiên."""
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


# Tiêu đề riêng (không trùng) cho từng câu đố mẫu.
TITLES = {
    "01-3x3-a": "The Penalty Conspiracy",
    "02-3x3-b": "The Offside Mystery",
    "03-3x3-c": "The Locker Room Riddle",
    "04-3x3-d": "The Golden Boot Affair",
    "05-4x4-a": "The Final Whistle Riddle",
    "06-4x4-b": "The Derby Day Heist",
    "07-4x4-c": "The Transfer Window Scandal",
    "08-4x4-d": "The Midnight Kickoff Affair",
    "09-5x5-a": "The Penalty Shootout Heist",
    "10-5x5-b": "The Extra Time Mystery",
    "90-3x3-ambiguous": "Failure case: The Twin Alibi",
    "91-3x3-inconsistent": "Failure case: The Forged Scoresheet",
}


def with_cast(puzzle: Puzzle) -> Puzzle:
    """Đặt tên, nghề theo bộ cầu thủ và tiêu đề riêng của câu đố (logic không đổi)."""
    puzzle.characters = themed_characters(puzzle, puzzle.characters, DEFAULT_THEME)
    puzzle.title = TITLES[puzzle.puzzle_id]
    return puzzle


def main() -> None:
    """Tạo mới toàn bộ 12 tệp JSON trong thư mục ``puzzles/`` từ seed cố định."""
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    for file_id, size, seed, min_waves in SPECS:
        puzzle = with_cast(generate(size, seed=seed, min_waves=min_waves, puzzle_id=file_id))
        puzzle.save(OUT / f"{file_id}.json")
        types = sorted({c.type for c in puzzle.clues.values() if c})
        print(f"{file_id}: {puzzle.title!r} waves={puzzle.meta['waves']} types={types}")
    for puzzle in (ambiguous_case(), inconsistent_case()):
        puzzle = with_cast(puzzle)
        puzzle.save(OUT / f"{puzzle.puzzle_id}.json")
        print(f"{puzzle.puzzle_id}: {puzzle.title!r}")


if __name__ == "__main__":
    main()
