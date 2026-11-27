"""Chạy thực nghiệm toàn hệ thống trên bộ câu đố mẫu và xuất số liệu/biểu đồ vào results/.

Cách sử dụng:
    python experiments.py                 # Chạy đầy đủ 3 cấu hình -> results/
    python experiments.py --quick         # Chỉ chạy cấu hình mặc định -> results/quick/

Với mỗi cặp (câu đố, cấu hình), LogicAgent tự động chơi qua GameEngine để đo
số biến, số mệnh đề CNF, số lần gọi SAT, thống kê DPLL, số bước/đợt (waves) và thời gian.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from griductive.agent import LogicAgent  # noqa: E402
from griductive.dpll import SolverTimeout  # noqa: E402
from griductive.engine import GameEngine  # noqa: E402
from griductive.generator import simulate_waves  # noqa: E402
from griductive.puzzle import Puzzle  # noqa: E402

CONFIGS = [
    # (nhãn hiển thị, chiến lược truy vấn, chế độ mã hóa đếm)
    ("filter+auto", "filter", "auto"),
    ("naive+auto", "naive", "auto"),
    ("filter+counter", "filter", "counter"),
]

FIELDS = ["puzzle", "size", "config", "outcome", "expected", "primary_vars", "aux_vars", "clauses",
          "sat_calls", "decisions", "propagations", "backtracks", "steps", "waves", "agent_sat_ms",
          "engine_sat_calls", "runtime_ms", "uniqueness", "uniqueness_sat_calls"]


def run_one(puzzle: Puzzle, label: str, strategy: str, cardinality: str, time_limit: float) -> dict:
    """Chạy một ván câu đố với một cấu hình và thu thập đầy đủ các chỉ số hiệu năng.

    * ``sat_calls`` / decisions / propagations / backtracks / ``agent_sat_ms``: số liệu của riêng LogicAgent.
    * ``engine_sat_calls``: số lượt truy vấn SAT mà GameEngine dùng để kiểm chứng độc lập từng phán đoán.
    * ``runtime_ms``: tổng thời gian thực của cả vòng lặp suy diễn (bao gồm Agent + Engine).
    * ``waves``: số đợt lật thẻ nếu mỗi đợt lật đồng loạt toàn bộ thẻ đang bị ép.
    """
    row = {"puzzle": puzzle.puzzle_id, "size": puzzle.board.size, "config": label,
           "expected": puzzle.meta.get("expected", "SOLVED")}
    engine = GameEngine(puzzle, strategy=strategy, cardinality=cardinality)
    agent = LogicAgent(strategy=strategy, cardinality=cardinality, time_limit=time_limit)
    start = time.perf_counter()
    try:
        report = agent.solve(engine.player_view())
    except Exception as exc:  # Giữ nguyên dòng lỗi trong bảng kết quả thay vì bỏ qua ca lỗi
        row["outcome"] = f"ERROR: {type(exc).__name__}: {exc}"
        return row

    row.update({
        "outcome": report.outcome,
        "primary_vars": report.max_kb["primary_vars"],
        "aux_vars": report.max_kb["aux_vars"],
        "clauses": report.max_kb["clauses"],
        "sat_calls": report.sat_calls,
        "decisions": report.solver.decisions,
        "propagations": report.solver.propagations,
        "backtracks": report.solver.backtracks,
        "steps": report.steps,
        "agent_sat_ms": round(report.solver.runtime * 1000, 1),
        "engine_sat_calls": engine.sat_calls,
        "runtime_ms": round((time.perf_counter() - start) * 1000, 1),
    })
    try:
        row["waves"] = simulate_waves(puzzle, strategy)[1]
    except Exception as exc:
        row["waves"] = f"ERROR: {exc}"
    try:
        uniq = engine.uniqueness(time_limit=time_limit)
        row["uniqueness"], row["uniqueness_sat_calls"] = uniq.verdict, uniq.sat_calls
    except SolverTimeout:
        row["uniqueness"] = "TIMEOUT"
    return row


# ------------------------------------------------------------------ Vẽ biểu đồ SVG
PALETTE = ["#4f6bed", "#e8743b", "#19a979"]


def bar_chart(title: str, rows: list[dict], metric: str, configs: list[str], log: bool = False) -> str:
    """Sinh biểu đồ cột SVG trực tiếp từ dữ liệu thực nghiệm (hỗ trợ thang tuyến tính và logarit)."""
    puzzles = list(dict.fromkeys(r["puzzle"] for r in rows))
    values = {(r["puzzle"], r["config"]): float(r.get(metric) or 0) for r in rows}
    vmax = max(values.values() or [1]) or 1
    scale = (lambda v: math.log10(1 + v) / math.log10(1 + vmax)) if log else (lambda v: v / vmax)
    width, height, left, bottom, top = 920, 360, 60, 70, 40
    plot_w, plot_h = width - left - 20, height - top - bottom
    group = plot_w / max(1, len(puzzles))
    bar = group * 0.8 / max(1, len(configs))

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" font-family="Inter,Helvetica,Arial,sans-serif" font-size="11">',
           f'<text x="{left}" y="22" font-size="15" font-weight="600" fill="#1f2433">{title}</text>',
           f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#9aa1b2"/>']
    for frac in (0.25, 0.5, 0.75, 1.0):
        y = top + plot_h * (1 - frac)
        if log:
            label = f"{(1 + vmax) ** frac - 1:,.0f}"
        else:
            label = f"{vmax * frac:,.0f}" if vmax >= 10 else f"{vmax * frac:.2f}"
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#e3e6ee"/>')
        out.append(f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" fill="#6b7285">{label}</text>')

    for gi, puzzle in enumerate(puzzles):
        gx = left + gi * group + group * 0.1
        for ci, cfg in enumerate(configs):
            v = values.get((puzzle, cfg), 0)
            h = plot_h * scale(v)
            x = gx + ci * bar
            out.append(f'<rect x="{x:.1f}" y="{top + plot_h - h:.1f}" width="{bar - 2:.1f}" height="{h:.1f}" rx="2" fill="{PALETTE[ci % 3]}"><title>{puzzle} / {cfg}: {v:g}</title></rect>')
        out.append(f'<text x="{gx + group * 0.4:.1f}" y="{top + plot_h + 16}" text-anchor="middle" fill="#3b4152">{puzzle.split("-")[0]}·{puzzle.split("-")[1]}</text>')

    lx = left
    for ci, cfg in enumerate(configs):
        out.append(f'<rect x="{lx}" y="{height - 22}" width="12" height="12" rx="2" fill="{PALETTE[ci % 3]}"/>')
        out.append(f'<text x="{lx + 18}" y="{height - 12}" fill="#3b4152">{cfg}</text>')
        lx += 150
    if log:
        out.append(f'<text x="{left + plot_w}" y="{height - 12}" text-anchor="end" fill="#6b7285">log scale</text>')
    out.append("</svg>")
    return "\n".join(out)


def markdown_table(rows: list[dict]) -> str:
    """Định dạng bảng kết quả thực nghiệm sang cú pháp Markdown."""
    cols = ["puzzle", "config", "outcome", "primary_vars", "aux_vars", "clauses", "sat_calls", "decisions",
            "propagations", "backtracks", "steps", "waves", "agent_sat_ms", "engine_sat_calls", "runtime_ms",
            "uniqueness"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)


def main() -> None:
    """Điểm vào CLI chạy thực nghiệm benchmark và ghi kết quả CSV/JSON/Markdown/SVG."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--puzzles", default=str(ROOT / "puzzles"))
    parser.add_argument("--out", default=str(ROOT / "results"))
    parser.add_argument("--quick", action="store_true", help="Chỉ chạy cấu hình mặc định filter+auto")
    parser.add_argument("--time-limit", type=float, default=30.0, help="Giới hạn giây cho mỗi lượt gọi SAT")
    args = parser.parse_args()

    configs = CONFIGS[:1] if args.quick else CONFIGS
    out = Path(args.out)
    if args.quick and args.out == str(ROOT / "results"):
        out = out / "quick"  # Không ghi đè bảng đối chiếu đầy đủ trong results/
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for path in sorted(Path(args.puzzles).glob("*.json")):
        puzzle = Puzzle.load(path)
        for label, strategy, cardinality in configs:
            row = run_one(puzzle, label, strategy, cardinality, args.time_limit)
            rows.append(row)
            print(f"{row['puzzle']:<22} {label:<15} {row['outcome']:<13} sat_calls={row.get('sat_calls', '-'):<5} "
                  f"aux={row.get('aux_vars', '-'):<4} clauses={row.get('clauses', '-'):<5} {row.get('runtime_ms', '-')} ms")

    with open(out / "experiments.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in FIELDS})
    (out / "experiments.json").write_text(json.dumps({
        "python": platform.python_version(), "platform": platform.platform(), "rows": rows}, indent=2))
    (out / "experiments.md").write_text(markdown_table(rows) + "\n", encoding="utf-8")
    labels = [c[0] for c in configs]
    solved = [r for r in rows if r.get("sat_calls") is not None]
    (out / "chart_sat_calls.svg").write_text(bar_chart("SAT calls per puzzle", solved, "sat_calls", labels))
    (out / "chart_runtime.svg").write_text(bar_chart("Agent SAT time (ms) per puzzle", solved, "agent_sat_ms", labels, log=True))
    (out / "chart_clauses.svg").write_text(bar_chart("CNF clauses in the final KB", solved, "clauses", labels, log=True))
    (out / "chart_propagations.svg").write_text(bar_chart("Unit propagations (all SAT calls)", solved, "propagations", labels, log=True))
    mismatches = [r for r in rows if r["outcome"] != r["expected"]]
    print(f"\n{len(rows)} runs written to {out}. Unexpected outcomes: {len(mismatches)}")
    for r in mismatches:
        print("  ", r["puzzle"], r["config"], r["outcome"], "expected", r["expected"])


if __name__ == "__main__":
    main()
