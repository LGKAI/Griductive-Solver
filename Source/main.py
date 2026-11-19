"""Casebook - a no-guess deduction solver (CSC14003 Project 2).

    python main.py                       # start the GUI at http://127.0.0.1:8765
    python main.py --port 9000 --no-browser
    python main.py --solve puzzles/05-4x4-a.json   # solve in the terminal, print the trace
    python main.py --check puzzles/05-4x4-a.json   # uniqueness check of the full clue set
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from griductive.agent import LogicAgent  # noqa: E402
from griductive.clues import clue_text  # noqa: E402
from griductive.engine import GameEngine, PuzzleIntegrityError  # noqa: E402
from griductive.puzzle import Puzzle, PuzzleError  # noqa: E402


def _names(puzzle: Puzzle, text: str) -> str:
    for cell, ch in puzzle.characters.items():
        text = text.replace("{" + cell + "}", f"{ch.name}({cell})")
    return text


def solve_cli(path: str, strategy: str, cardinality: str, verbose: bool) -> int:
    puzzle = Puzzle.load(path)
    engine = GameEngine(puzzle, strategy, cardinality)
    print(f"{puzzle.title}  [{puzzle.board.size}x{puzzle.board.size}]  strategy={strategy} cardinality={cardinality}")
    for cell in puzzle.initial:
        clue = puzzle.clues[cell]
        print(f"  face-up {cell} {puzzle.characters[cell].name}: {_names(puzzle, clue_text(clue)) if clue else '-'}")
    report = LogicAgent(strategy, cardinality).solve(engine.player_view())
    for entry in report.trace:
        kb = entry.kb_stats
        head = f"step {entry.step:>2}: {entry.result:<12}"
        if entry.cell:
            head += f" {entry.verdict:<9} {entry.name}({entry.cell})"
        print(f"{head}  | SAT calls={len(entry.sat_queries):<3} vars={kb.get('primary_vars', 0)}+{kb.get('aux_vars', 0)} "
              f"clauses={kb.get('clauses', 0)}")
        if verbose:
            print(f"         active clues: {', '.join(entry.active_clues)}")
            for q in entry.sat_queries:
                print(f"         {q['query']:<16} -> {q['result']}")
        if entry.revealed_text:
            print(f"         revealed: {_names(puzzle, entry.revealed_text)}")
    s = report.solver
    print(f"\noutcome={report.outcome} steps={report.steps} sat_calls={report.sat_calls} "
          f"decisions={s.decisions} propagations={s.propagations} backtracks={s.backtracks} "
          f"runtime={report.runtime * 1000:.1f} ms")
    return 0 if report.outcome == "SOLVED" else 1


def check_cli(path: str, cardinality: str) -> int:
    puzzle = Puzzle.load(path)
    res = GameEngine(puzzle, cardinality=cardinality).uniqueness()
    print(f"{puzzle.title}: {res.verdict} ({res.count} solution(s) found, {res.sat_calls} SAT calls)")
    return 0 if res.unique else 1


def serve(host: str, port: int, open_browser: bool) -> int:
    from griductive.server import make_server

    server = None
    for candidate in range(port, port + 20):
        try:
            server = make_server(host, candidate)
            break
        except OSError:
            continue
    if server is None:
        print(f"No free port in {port}-{port + 19}.", file=sys.stderr)
        return 1
    url = f"http://{host}:{server.server_address[1]}/"
    print(f"Casebook GUI running at {url}  (Ctrl+C to stop)", flush=True)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Casebook: a no-guess Griductive-style solver")
    parser.add_argument("--solve", metavar="PUZZLE.json", help="solve a puzzle in the terminal")
    parser.add_argument("--check", metavar="PUZZLE.json", help="check uniqueness of a puzzle's full clue set")
    parser.add_argument("--strategy", choices=["filter", "naive"], default="filter")
    parser.add_argument("--cardinality", choices=["auto", "direct", "counter"], default="auto")
    parser.add_argument("-v", "--verbose", action="store_true", help="print every SAT query in --solve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.solve:
            return solve_cli(args.solve, args.strategy, args.cardinality, args.verbose)
        if args.check:
            return check_cli(args.check, args.cardinality)
    except (OSError, PuzzleError, PuzzleIntegrityError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return serve(args.host, args.port, not args.no_browser)


if __name__ == "__main__":
    sys.exit(main())
