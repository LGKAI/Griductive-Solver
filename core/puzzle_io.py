"""
Module đọc và ghi dữ liệu câu đố Griductive ra/vào định dạng tệp tin JSON.
Hỗ trợ chức năng Lưu (Save) và Tải màn chơi (Load) từ giao diện người dùng.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .models import Character, Clue, ClueKind, Puzzle, Status


def puzzle_to_dict(puzzle: Puzzle) -> dict[str, Any]:
    """Chuyển đổi đối tượng Puzzle thành một từ điển (dictionary) chuẩn JSON."""
    return {
        "id": puzzle.id,
        "title": puzzle.title,
        "rows": puzzle.rows,
        "columns": puzzle.columns,
        "seed": puzzle.seed,
        "initially_revealed": list(puzzle.initially_revealed),
        "characters": [
            {
                "cell": char.cell,
                "name": char.name,
                "profession": char.profession,
                "portrait_index": char.portrait_index,
            }
            for char in puzzle.characters
        ],
        "solution": {cell: status.value for cell, status in puzzle.solution.items()},
        "clues": {
            cell: {
                "id": clue.id,
                "owner": clue.owner,
                "kind": clue.kind.value,
                "targets": list(clue.targets),
                "status": clue.status.value if clue.status else None,
                "region_type": clue.region_type,
                "region": list(clue.region),
                "k": clue.k,
                "parity": clue.parity,
                "region_b": list(clue.region_b),
                "comparison": clue.comparison,
            }
            for cell, clue in puzzle.clues.items()
        },
    }


def dict_to_puzzle(data: dict[str, Any]) -> Puzzle:
    """Khôi phục đối tượng Puzzle từ dữ liệu từ điển JSON đã đọc."""
    characters = tuple(
        Character(
            cell=item["cell"],
            name=item["name"],
            profession=item["profession"],
            portrait_index=item.get("portrait_index", 0),
        )
        for item in data["characters"]
    )

    solution = {cell: Status(status_str) for cell, status_str in data["solution"].items()}

    clues: dict[str, Clue] = {}
    for cell, c in data["clues"].items():
        clues[cell] = Clue(
            id=c["id"],
            owner=c["owner"],
            kind=ClueKind(c["kind"]),
            targets=tuple(c.get("targets", ())),
            status=Status(c["status"]) if c.get("status") else None,
            region_type=c.get("region_type", "EXPLICIT"),
            region=tuple(c.get("region", ())),
            k=c.get("k"),
            parity=c.get("parity"),
            region_b=tuple(c.get("region_b", ())),
            comparison=c.get("comparison"),
        )

    return Puzzle(
        id=data["id"],
        title=data.get("title", f"Vụ án {data['rows']}x{data['columns']}"),
        rows=data["rows"],
        columns=data["columns"],
        characters=characters,
        clues=clues,
        solution=solution,
        initially_revealed=tuple(data["initially_revealed"]),
        seed=data.get("seed", 0),
    )


def save_puzzle_to_json(puzzle: Puzzle, path: str | Path) -> None:
    """Lưu trữ câu đố ra tệp tin JSON."""
    data = puzzle_to_dict(puzzle)
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_puzzle_from_json(path: str | Path) -> Puzzle:
    """Đọc và phục hồi câu đố từ một tệp tin JSON."""
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return dict_to_puzzle(data)
