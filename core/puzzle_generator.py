"""
Trình tạo câu đố Griductive ngẫu nhiên (Puzzle Generator).
Tự động tạo câu đố có nghiệm duy nhất và đảm bảo giải được tuần tự không cần đoán mò.
Ánh xạ chính xác chân dung và tên của 25 siêu sao bóng đá thế giới.
"""
from __future__ import annotations

from random import Random, SystemRandom
from typing import Sequence

from .clues import evaluate_clue
from .models import Character, Clue, ClueKind, Puzzle, Status
from .regions import (
    boundary_region,
    cell_to_coord,
    column_region,
    coord_to_cell,
    corners_region,
    explicit_region,
    neighbors_region,
    row_region,
)

# Danh sách tên 25 cầu thủ bóng đá theo đúng thứ tự ảnh chân dung lưới 5x5
NAMES = (
    "Messi", "Ronaldo", "Neymar", "Mbappe", "Suarez",
    "Kane", "Lewandowski", "Ramos", "Benzema", "Modric",
    "Griezmann", "Haaland", "De Bruyne", "Salah", "Vinicius",
    "Bernardo", "Kroos", "Alaba", "Kimmich", "Valverde",
    "Hakimi", "Musiala", "Pedri", "Gavi", "Rodrygo",
)

# Vị trí thi đấu và đội tuyển quốc gia tương ứng của từng cầu thủ
PROFESSIONS = (
    "Forward (Argentina)", "Forward (Portugal)", "Forward (Brazil)", "Forward (France)", "Striker (Uruguay)",
    "Striker (England)", "Striker (Poland)", "Defender (Spain)", "Striker (France)", "Midfielder (Croatia)",
    "Forward (France)", "Striker (Norway)", "Midfielder (Belgium)", "Forward (Egypt)", "Winger (Brazil)",
    "Midfielder (Portugal)", "Midfielder (Germany)", "Defender (Austria)", "Midfielder (Germany)", "Midfielder (Uruguay)",
    "Defender (Morocco)", "Midfielder (Germany)", "Midfielder (Spain)", "Midfielder (Spain)", "Forward (Brazil)",
)

# Các loại manh mối được sử dụng luân phiên
CLUE_KINDS = (
    ClueKind.FACT,
    ClueKind.SAME,
    ClueKind.DIFFERENT,
    ClueKind.EXACTLY,
    ClueKind.AT_LEAST,
    ClueKind.AT_MOST,
    ClueKind.PARITY,
    ClueKind.COUNT_COMPARE,
)


def _grid_cells(rows: int, columns: int) -> tuple[str, ...]:
    """Tạo danh sách toàn bộ các tọa độ ô trên bàn cờ."""
    return tuple(coord_to_cell(col, r) for r in range(rows) for col in range(columns))


def _make_chain_clue(
    clue_id: str,
    owner: str,
    target: str,
    preceding_known: tuple[str, ...],
    owner_status: Status,
    target_status: Status,
    solution: dict[str, Status],
    kind: ClueKind,
    rng: Random,
) -> Clue:
    """Tạo manh mối do ô `owner` sở hữu, có tính chất ràng buộc bắt buộc ô `target`
    ngay khi các ô tiền nhiệm trong chuỗi đã được lật mở."""
    if kind is ClueKind.FACT:
        return Clue(
            id=clue_id,
            owner=owner,
            kind=ClueKind.FACT,
            targets=(target,),
            status=target_status,
        )

    if kind is ClueKind.SAME:
        relation = ClueKind.SAME if owner_status is target_status else ClueKind.DIFFERENT
        return Clue(
            id=clue_id,
            owner=owner,
            kind=relation,
            targets=(target, owner),
        )

    if kind is ClueKind.DIFFERENT:
        relation = ClueKind.DIFFERENT if owner_status is not target_status else ClueKind.SAME
        return Clue(
            id=clue_id,
            owner=owner,
            kind=relation,
            targets=(target, owner),
        )

    # Đối với các manh mối vùng và đếm, kết hợp ô owner và một số ô đã biết trước đó
    pool = [owner]
    if preceding_known:
        valid_preds = [c for c in preceding_known if c != target and c != owner]
        sample_k = min(len(valid_preds), rng.randint(0, 2))
        if sample_k > 0:
            pool.extend(rng.sample(valid_preds, sample_k))

    region = explicit_region((target,) + tuple(pool))
    actual_criminals = sum(1 for c in region if solution[c] is Status.CRIMINAL)
    target_is_crm = (target_status is Status.CRIMINAL)

    if kind is ClueKind.EXACTLY:
        return Clue(
            id=clue_id,
            owner=owner,
            kind=ClueKind.EXACTLY,
            region_type="EXPLICIT",
            region=region,
            k=actual_criminals,
        )

    if kind is ClueKind.AT_LEAST:
        if target_is_crm:
            return Clue(
                id=clue_id,
                owner=owner,
                kind=ClueKind.AT_LEAST,
                region_type="EXPLICIT",
                region=region,
                k=actual_criminals,
            )
        return Clue(
            id=clue_id,
            owner=owner,
            kind=ClueKind.AT_MOST,
            region_type="EXPLICIT",
            region=region,
            k=actual_criminals,
        )

    if kind is ClueKind.AT_MOST:
        if not target_is_crm:
            return Clue(
                id=clue_id,
                owner=owner,
                kind=ClueKind.AT_MOST,
                region_type="EXPLICIT",
                region=region,
                k=actual_criminals,
            )
        return Clue(
            id=clue_id,
            owner=owner,
            kind=ClueKind.AT_LEAST,
            region_type="EXPLICIT",
            region=region,
            k=actual_criminals,
        )

    if kind is ClueKind.PARITY:
        parity_str = "ODD" if actual_criminals % 2 != 0 else "EVEN"
        return Clue(
            id=clue_id,
            owner=owner,
            kind=ClueKind.PARITY,
            region_type="EXPLICIT",
            region=region,
            parity=parity_str,
        )

    # Phần mở rộng COUNT_COMPARE
    comp = "EQ" if target_status is owner_status else (
        "GT" if target_status is Status.CRIMINAL else "LT"
    )
    return Clue(
        id=clue_id,
        owner=owner,
        kind=ClueKind.COUNT_COMPARE,
        region_type="EXPLICIT",
        region=(target,),
        region_b=(owner,),
        comparison=comp,
    )


def generate_puzzle(
    seed: int | None = None,
    rows: int = 3,
    columns: int = 3,
) -> Puzzle:
    """Tạo một ván chơi mới tái lập được, bảo đảm có nghiệm duy nhất
    và 100% giải được tuần tự mà không cần phỏng đoán."""
    actual_seed = seed if seed is not None else SystemRandom().randrange(1, 2**31)
    rng = Random(actual_seed)

    if not (3 <= rows <= 5) or not (3 <= columns <= 5):
        raise ValueError(f"Kích thước bàn cờ phải nằm trong khoảng [3, 5], nhận {rows}x{columns}.")

    cells = _grid_cells(rows, columns)
    num_cells = len(cells)

    # Chọn ngẫu nhiên danh sách cầu thủ cho số ô của bàn cờ
    roster_indices = list(range(len(NAMES)))
    rng.shuffle(roster_indices)
    chosen_indices = roster_indices[:num_cells]

    characters = tuple(
        Character(
            cell=cell,
            name=NAMES[idx],
            profession=PROFESSIONS[idx],
            portrait_index=idx,
        )
        for cell, idx in zip(cells, chosen_indices)
    )

    # Sinh đáp án ẩn: Đảm bảo có cả Criminal và Innocent
    solution_vals = [rng.choice((True, False)) for _ in cells]
    if not any(solution_vals):
        solution_vals[0] = True
    elif all(solution_vals):
        solution_vals[0] = False

    solution = {cell: Status.from_boolean(val) for cell, val in zip(cells, solution_vals)}

    # Xây dựng 2 nhánh suy luận độc lập xuất phát từ 2 thẻ mở mặt ban đầu
    reveal_order = list(cells)
    rng.shuffle(reveal_order)
    roots = (reveal_order[0], reveal_order[1])
    paths: list[list[str]] = [[roots[0]], [roots[1]]]

    for index, cell in enumerate(reveal_order[2:]):
        paths[index % 2].append(cell)

    kinds = [CLUE_KINDS[i % len(CLUE_KINDS)] for i in range(num_cells)]
    rng.shuffle(kinds)

    clues: dict[str, Clue] = {}
    clue_idx = 0
    for path in paths:
        # Chuỗi suy luận tuần tự từng bước
        for idx in range(len(path) - 1):
            owner = path[idx]
            target = path[idx + 1]
            clue_id = f"CLUE-{clue_idx + 1:02d}"
            clue = _make_chain_clue(
                clue_id=clue_id,
                owner=owner,
                target=target,
                preceding_known=tuple(path[:idx]),
                owner_status=solution[owner],
                target_status=solution[target],
                solution=solution,
                kind=kinds[clue_idx % len(kinds)],
                rng=rng,
            )
            clues[owner] = clue
            clue_idx += 1

        # Ô cuối cùng trong nhánh cung cấp manh mối FACT neo về ô gốc (root),
        # khép kín chu trình logic và bảo đảm bài toán có nghiệm duy nhất toàn cục.
        last_cell = path[-1]
        clue_id = f"CLUE-{clue_idx + 1:02d}"
        root_cell = path[0]
        clues[last_cell] = Clue(
            id=clue_id,
            owner=last_cell,
            kind=ClueKind.FACT,
            targets=(root_cell,),
            status=solution[root_cell],
        )
        clue_idx += 1

    case_hex = f"{actual_seed:08X}"
    return Puzzle(
        id=f"case-{rows}x{columns}-{case_hex}",
        title=f"Vụ Án {rows}x{columns} (#{case_hex[:6]})",
        rows=rows,
        columns=columns,
        characters=characters,
        clues=clues,
        solution=solution,
        initially_revealed=roots,
        seed=actual_seed,
    )


def create_sample_puzzles() -> list[Puzzle]:
    """Tạo bộ câu đố mẫu cố định phục vụ kiểm thử và báo cáo thực nghiệm (3x3, 3x4, 4x4, 5x5)."""
    return [
        generate_puzzle(seed=3003, rows=3, columns=3),
        generate_puzzle(seed=3004, rows=3, columns=4),
        generate_puzzle(seed=4004, rows=4, columns=4),
        generate_puzzle(seed=5005, rows=5, columns=5),
    ]
