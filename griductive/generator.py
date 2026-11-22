"""Bộ sinh câu đố ngẫu nhiên bảo đảm giải được 100% không cần đoán mò.

Quy trình sinh câu đố:
1. Sinh ngẫu nhiên một đáp án ẩn hợp lệ (tỷ lệ tội phạm 35–60%).
2. Gán cho mỗi ô một manh mối ngẫu nhiên đúng trên đáp án đó.
3. Mô phỏng người chơi không đoán mò (mỗi đợt lật đồng loạt các thẻ đang bị ép).
4. Nếu bế tắc (STUCK), thay ngẫu nhiên manh mối của một thẻ đã lật rồi mô phỏng lại.

Mọi câu đố giải hết trong bước mô phỏng đều chắc chắn giải được bằng suy luận thuần túy
và có nghiệm duy nhất (vì mọi biến đều đã bị kéo theo).
"""

from __future__ import annotations

import random
from typing import Optional

from .board import Board
from .clues import CRIMINAL, INNOCENT, ClueError, evaluate, parse_clue
from .entailment import CRIMINAL_V, INNOCENT_V, analyze
from .knowledge import PublicCharacter, PublicState
from .puzzle import Puzzle, name_key

NAMES = [
    "Abel", "Ada", "Alma", "Basil", "Bea", "Bruno", "Cleo", "Cyrus", "Dara", "Dmitri", "Edda", "Elio",
    "Faye", "Felix", "Greta", "Gus", "Hana", "Hugo", "Ines", "Ivo", "Jade", "Jonah", "Kira", "Kofi",
    "Lena", "Lior", "Mila", "Milo", "Nadia", "Nico", "Odile", "Omar", "Pia", "Pavel", "Quinn", "Rosa",
    "Rufus", "Sana", "Silas", "Tamsin", "Theo", "Uma", "Viggo", "Vera", "Wren", "Xavi", "Yara", "Zane",
]
PROFESSIONS = [
    "Baker", "Pilot", "Chemist", "Florist", "Guard", "Judge", "Mechanic", "Painter", "Sailor", "Tailor",
    "Clerk", "Farmer", "Doctor", "Butler", "Coder", "Singer", "Banker", "Chef", "Miner", "Writer",
]
CASE_WORDS = ["Velvet", "Silent", "Copper", "Midnight", "Hollow", "Crimson", "Glass", "Ivory", "Paper",
              "Lantern", "Marble", "Ember", "Willow", "Harbor", "Clockwork", "Saffron"]
CASE_NOUNS = ["Ledger", "Orchard", "Gallery", "Station", "Masquerade", "Archive", "Garden", "Mill",
              "Theatre", "Market", "Vault", "Lighthouse"]


class GenerationFailed(RuntimeError):
    """Ngoại lệ khi không tìm được câu đố thỏa mãn trong số lần thử cho phép."""


# ---------------------------------------------------------------- Sinh manh mối ngẫu nhiên
def _pick_region(rng: random.Random, board: Board, owner: str) -> dict:
    """Chọn ngẫu nhiên một biểu thức vùng (bao gồm cả các vùng cốt lõi lẫn vùng mở rộng)."""
    cells = board.cells
    other = rng.choice([c for c in cells if c != owner])
    col, row = board.coords(owner)
    roll = rng.random()
    if roll < 0.30:
        return {"kind": "neighbors", "of": owner if rng.random() < 0.6 else other}
    if roll < 0.45:
        return {"kind": "row", "index": row + 1 if rng.random() < 0.6 else rng.randint(1, board.size)}
    if roll < 0.60:
        letter = owner[0] if rng.random() < 0.6 else rng.choice("ABCDEFGHIJ"[: board.size])
        return {"kind": "col", "index": letter}
    if roll < 0.66:
        return {"kind": "corners"}
    if roll < 0.70:
        return {"kind": "edge"}
    if roll < 0.78:
        return {"kind": "ray", "of": rng.choice([owner, other]), "dir": rng.choice(["left", "right", "above", "below"])}
    if roll < 0.83:
        a = rng.choice(cells)
        line = [c for c in cells if c != a and (c[0] == a[0] or c[1:] == a[1:])]
        return {"kind": "between", "a": a, "b": rng.choice(line)}
    if roll < 0.88:
        return {"kind": "common_neighbors", "a": owner, "b": other}
    if roll < 0.95:
        line = {"kind": "row", "index": rng.randint(1, board.size)} if rng.random() < 0.5 else \
            {"kind": "col", "index": rng.choice("ABCDEFGHIJ"[: board.size])}
        return {"kind": "intersect", "regions": [{"kind": "neighbors", "of": rng.choice([owner, other])}, line]}
    sample = rng.sample(list(cells), rng.randint(2, min(4, len(cells))))
    return {"kind": "cells", "cells": sample}


def random_clue(rng: random.Random, board: Board, owner: str, solution: dict[str, bool],
                tries: int = 200) -> dict:
    """Sinh một manh mối ngẫu nhiên không tầm thường và đúng trên ``solution``."""
    cells = board.cells
    for _ in range(tries):
        who = CRIMINAL if rng.random() < 0.65 else INNOCENT
        want = who == CRIMINAL
        roll = rng.random()
        other = rng.choice([c for c in cells if c != owner])
        near = [c for c in board.neighbors(owner)]
        if roll < 0.50:
            region = _pick_region(rng, board, owner)
            try:
                rcells = parse_clue(board, {"type": "PARITY", "parity": "odd", "region": region}).params["region"]
            except ClueError:
                continue
            count = sum(1 for c in rcells if solution[c] == want)
            kind = rng.choices(["EXACTLY", "AT_LEAST", "AT_MOST"], weights=[6, 2, 2])[0]
            if kind == "EXACTLY":
                k = count
            elif kind == "AT_LEAST":
                k = count - rng.randint(0, 1)
                if k <= 0:
                    continue
            else:
                k = count + rng.randint(0, 1)
                if k >= len(rcells):
                    continue
            if len(rcells) < 2:
                continue
            data = {"type": kind, "k": k, "region": region, "who": who}
        elif roll < 0.66:
            b = rng.choice(near) if rng.random() < 0.6 else other
            a = owner if rng.random() < 0.3 else rng.choice([c for c in cells if c != b])
            data = {"type": "SAME" if solution[a] == solution[b] else "DIFFERENT", "a": a, "b": b}
        elif roll < 0.73:
            region = _pick_region(rng, board, owner)
            data = {"type": "PARITY", "parity": "odd", "region": region, "who": who}
            try:
                rcells = parse_clue(board, data).params["region"]
            except ClueError:
                continue
            if len(rcells) < 2:
                continue
            data["parity"] = "odd" if sum(1 for c in rcells if solution[c] == want) % 2 else "even"
        elif roll < 0.82:
            left, right = _pick_region(rng, board, owner), _pick_region(rng, board, other)
            data = {"type": "COMPARE", "op": "equal", "left": left, "right": right, "who": who}
            try:
                parsed = parse_clue(board, data)
            except ClueError:
                continue
            if set(parsed.params["left"]) == set(parsed.params["right"]):
                continue
            lc = sum(1 for c in parsed.params["left"] if solution[c] == want)
            rc = sum(1 for c in parsed.params["right"] if solution[c] == want)
            data["op"] = "more" if lc > rc else "fewer" if lc < rc else "equal"
        elif roll < 0.90:
            col, row = board.coords(owner)
            region = rng.choice([{"kind": "row", "index": row + 1}, {"kind": "col", "index": owner[0]},
                                 {"kind": "ray", "of": owner, "dir": rng.choice(["left", "right", "above", "below"])}])
            data = {"type": "CONNECTED", "region": region, "who": who}
            try:
                parsed = parse_clue(board, data)
            except ClueError:
                continue
            members = [c for c in parsed.params["region"] if solution[c] == want]
            if len(parsed.params["region"]) < 3 or len(members) < 2:
                continue
        elif roll < 0.96:
            a, b = rng.sample(list(cells), 2)
            sa = CRIMINAL if solution[a] else INNOCENT
            if rng.random() < 0.5:  # Nếu tiền đề đúng -> kết luận bắt buộc đúng
                sb = CRIMINAL if solution[b] else INNOCENT
            else:  # Nếu tiền đề sai -> kết luận tùy ý vẫn hợp lệ
                sa = INNOCENT if solution[a] else CRIMINAL
                sb = rng.choice([CRIMINAL, INNOCENT])
            data = {"type": "IMPLIES", "if": {"cell": a, "status": sa}, "then": {"cell": b, "status": sb}}
        else:
            target = rng.choice([c for c in cells if c != owner])
            data = {"type": "FACT", "cell": target, "status": CRIMINAL if solution[target] else INNOCENT}
        try:
            clue = parse_clue(board, data, owner)
        except ClueError:
            continue
        if evaluate(clue, solution):
            return data
    raise GenerationFailed(f"could not build a clue for {owner}")


# ----------------------------------------------------------- Mô phỏng giải theo đợt (wave)
def simulate_waves(puzzle: Puzzle, strategy: str = "filter") -> tuple[bool, int, set[str]]:
    """Mô phỏng người chơi không đoán mò khi lật đồng loạt toàn bộ thẻ bị ép mỗi đợt.

    Trả về bộ ba ``(solved, waves, revealed_cells)``.
    """
    board = puzzle.board
    chars = tuple(PublicCharacter(c, ch.name, ch.profession) for c, ch in puzzle.characters.items())
    verdicts = {c: puzzle.solution[c] for c in puzzle.initial}
    waves = 0
    while len(verdicts) < len(board.cells):
        clues = [puzzle.clues[c] for c in verdicts if puzzle.clues[c] is not None]
        state = PublicState.make(board.size, chars, clues, verdicts)
        analysis = analyze(state, strategy)
        if not analysis.consistent:
            return False, waves, set(verdicts)
        forced = analysis.forced
        if not forced:
            return False, waves, set(verdicts)
        waves += 1
        for cell, verdict in forced:
            if (verdict == CRIMINAL_V) != puzzle.solution[cell] or verdict not in (CRIMINAL_V, INNOCENT_V):
                raise AssertionError("entailed verdict disagrees with the solution")
            verdicts[cell] = puzzle.solution[cell]
    return True, waves, set(verdicts)


# ------------------------------------------------------------ Bộ sinh chính
def generate(size: int, seed: Optional[int] = None, min_waves: Optional[int] = None,
             max_attempts: int = 40, max_repairs: int = 80, puzzle_id: Optional[str] = None) -> Puzzle:
    """Sinh câu đố kích thước ``size x size`` giải được hoàn toàn không đoán mò với độ sâu tối thiểu ``min_waves``."""
    rng = random.Random(seed)
    board = Board(size)
    cells = board.cells
    min_waves = size if min_waves is None else min_waves
    best: Optional[Puzzle] = None
    best_waves = -1
    for attempt in range(max_attempts):
        n = len(cells)
        criminals = rng.randint(max(2, round(n * 0.35)), min(n - 2, round(n * 0.6)))
        crim_cells = set(rng.sample(list(cells), criminals))
        solution = {c: c in crim_cells for c in cells}
        clues = {c: random_clue(rng, board, c, solution) for c in cells}
        initial = [rng.choice(cells)]
        names = sorted(rng.sample(NAMES, n), key=name_key)
        title = f"The {rng.choice(CASE_WORDS)} {rng.choice(CASE_NOUNS)}"
        professions = [rng.choice(PROFESSIONS) for _ in cells]
        for _ in range(max_repairs):
            data = {
                "id": puzzle_id or f"gen-{size}x{size}-{seed}",
                "title": title,
                "size": size,
                "initial": initial,
                "meta": {"generator_seed": seed, "attempt": attempt},
                "characters": [
                    {"cell": c, "name": names[i], "profession": professions[i],
                     "status": CRIMINAL if solution[c] else INNOCENT, "clue": clues[c]}
                    for i, c in enumerate(cells)
                ],
            }
            puzzle = Puzzle.from_dict(data)
            solved, waves, revealed = simulate_waves(puzzle)
            if solved:
                puzzle.meta["waves"] = waves
                if waves >= min_waves:
                    return puzzle
                if waves > best_waves:
                    best, best_waves = puzzle, waves
                # Câu đố giải được nhưng còn nông: đổi thử 1 manh mối để kéo dài chuỗi suy luận
                target = rng.choice([c for c in cells if c not in initial])
            else:
                target = rng.choice(sorted(revealed))
            clues[target] = random_clue(rng, board, target, solution)
    if best is not None:
        return best
    raise GenerationFailed(f"no solvable {size}x{size} puzzle found (seed={seed})")
