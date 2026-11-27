"""Bộ kiểm thử tính đúng đắn cho toàn bộ lõi logic. Chạy bằng: python -m unittest discover -s tests -v"""

from __future__ import annotations

import itertools
import json
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from griductive.agent import LogicAgent, SOLVED  # noqa: E402
from griductive.board import Board, RegionError, resolve_region  # noqa: E402
from griductive.clues import ClueError, evaluate, parse_clue, clue_text  # noqa: E402
from griductive.cnf import CNF, ClueEncoder, VarMap, encode_at_least, encode_at_most  # noqa: E402
from griductive.dpll import DPLLSolver  # noqa: E402
from griductive.engine import ACCEPTED, CONTRADICTED, NOT_PROVABLE, ALREADY_KNOWN, GameEngine  # noqa: E402
from griductive.entailment import analyze, check_uniqueness, is_entailed, minimal_support  # noqa: E402
from griductive.generator import random_clue, generate  # noqa: E402
from griductive.knowledge import PublicState  # noqa: E402
from griductive.puzzle import Puzzle, PuzzleError, name_key  # noqa: E402
from griductive.themes import THEMES, themed_characters  # noqa: E402

PUZZLE_DIR = ROOT / "puzzles"


def brute_sat(num_vars, clauses):
    for values in itertools.product((False, True), repeat=num_vars):
        if all(any((l > 0) == values[abs(l) - 1] for l in c) for c in clauses):
            return True
    return False


def satisfies(model, clauses):
    return all(any(model[abs(l)] == (l > 0) for l in c) for c in clauses)


class BoardTests(unittest.TestCase):
    def test_neighbors_counts(self):
        b = Board(4)
        self.assertEqual(len(b.neighbors("A1")), 3)
        self.assertEqual(len(b.neighbors("B1")), 5)
        self.assertEqual(len(b.neighbors("B2")), 8)
        self.assertNotIn("B2", b.neighbors("B2"))

    def test_rows_columns_order(self):
        b = Board(3)
        self.assertEqual(b.cells, ("A1", "B1", "C1", "A2", "B2", "C2", "A3", "B3", "C3"))
        self.assertEqual(b.row(2), ("A2", "B2", "C2"))
        self.assertEqual(b.column("C"), ("C1", "C2", "C3"))
        self.assertEqual(b.coords("C2"), (2, 1))

    def test_extended_regions(self):
        b = Board(4)
        self.assertEqual(resolve_region(b, {"kind": "corners"}), ("A1", "D1", "A4", "D4"))
        self.assertEqual(len(resolve_region(b, {"kind": "edge"})), 12)
        self.assertEqual(resolve_region(b, {"kind": "ray", "of": "B2", "dir": "right"}), ("C2", "D2"))
        self.assertEqual(resolve_region(b, {"kind": "ray", "of": "B2", "dir": "above"}), ("B1",))
        self.assertEqual(resolve_region(b, {"kind": "between", "a": "A3", "b": "D3"}), ("B3", "C3"))
        self.assertEqual(resolve_region(b, {"kind": "common_neighbors", "a": "A1", "b": "C1"}), ("B1", "B2"))
        inter = {"kind": "intersect", "regions": [{"kind": "neighbors", "of": "B2"}, {"kind": "col", "index": "A"}]}
        self.assertEqual(resolve_region(b, inter), ("A1", "A2", "A3"))
        minus = {"kind": "minus", "base": {"kind": "row", "index": 1}, "remove": {"kind": "corners"}}
        self.assertEqual(resolve_region(b, minus), ("B1", "C1"))

    def test_invalid_regions(self):
        b = Board(3)
        for spec in ({"kind": "row", "index": 4}, {"kind": "col", "index": "D"}, {"kind": "neighbors", "of": "Z9"},
                     {"kind": "cells", "cells": ["A1", "A1"]}, {"kind": "between", "a": "A1", "b": "B2"},
                     {"kind": "nope"}, {"kind": "row"}, {"kind": "row", "index": True}):
            with self.assertRaises(RegionError, msg=str(spec)):
                resolve_region(b, spec)


class ClueValidationTests(unittest.TestCase):
    def test_rejects_bad_clues(self):
        b = Board(3)
        bad = [
            {"type": "EXACTLY", "k": 4, "region": {"kind": "row", "index": 1}},
            {"type": "EXACTLY", "k": -1, "region": {"kind": "row", "index": 1}},
            {"type": "SAME", "a": "A1", "b": "A1"},
            {"type": "FACT", "cell": "A1", "status": "guilty"},
            {"type": "CONNECTED", "region": {"kind": "corners"}},
            {"type": "MAYBE"},
            {"type": "AT_MOST", "k": "1", "region": {"kind": "row", "index": 1}},
            {"type": "COMPARE", "op": "bigger", "left": {"kind": "row", "index": 1}, "right": {"kind": "row", "index": 2}},
        ]
        for data in bad:
            with self.assertRaises(ClueError, msg=str(data)):
                parse_clue(b, data, "A1")

    def test_text_rendering(self):
        b = Board(3)
        c = parse_clue(b, {"type": "EXACTLY", "k": 0, "region": {"kind": "col", "index": "B"}}, "A1")
        self.assertEqual(clue_text(c), "There are no criminals in column B")
        c = parse_clue(b, {"type": "AT_LEAST", "k": 1, "region": {"kind": "neighbors", "of": "B2"}, "who": "innocent"}, "A1")
        self.assertEqual(clue_text(c), "At least 1 innocent in {B2}'s neighbors")


class EncoderTests(unittest.TestCase):
    """The CNF of a clue, restricted to primary variables, must agree with the
    direct semantic evaluator on every complete assignment."""

    def _check(self, board, clue, assignments, modes=("direct", "counter", "auto")):
        varmap = VarMap(board)
        for mode in modes:
            cnf = CNF(varmap.num_primary)
            ClueEncoder(varmap, mode).encode(cnf, clue)
            solver = DPLLSolver(cnf.num_vars, cnf.clauses)
            for assignment in assignments:
                assumptions = [varmap.var(c) if v else -varmap.var(c) for c, v in assignment.items()]
                res = solver.solve(assumptions)
                expected = evaluate(clue, assignment)
                self.assertEqual(res.sat, expected,
                                 f"{mode} {clue.raw} under {assignment}: CNF={res.sat} eval={expected}")
                if res.sat:
                    self.assertTrue(satisfies(res.model, cnf.clauses))

    def test_random_clues_exhaustive_3x3(self):
        rng = random.Random(7)
        b = Board(3)
        all_assignments = [dict(zip(b.cells, v)) for v in itertools.product((False, True), repeat=9)]
        seen_types = set()
        for i in range(70):
            solution = rng.choice(all_assignments)
            data = random_clue(rng, b, rng.choice(b.cells), solution)
            clue = parse_clue(b, data, "A1")
            seen_types.add(clue.type)
            self._check(b, clue, all_assignments)
        self.assertGreaterEqual(len(seen_types), 8, seen_types)

    def test_every_template_exhaustive(self):
        b = Board(3)
        all_assignments = [dict(zip(b.cells, v)) for v in itertools.product((False, True), repeat=9)]
        nb = {"kind": "neighbors", "of": "B2"}
        templates = [
            {"type": "FACT", "cell": "B2", "status": "innocent"},
            {"type": "SAME", "a": "A1", "b": "C3"},
            {"type": "DIFFERENT", "a": "A1", "b": "B1"},
            {"type": "PARITY", "parity": "even", "region": {"kind": "all"}, "who": "innocent"},
            {"type": "COMPARE", "op": "more", "left": {"kind": "row", "index": 1}, "right": {"kind": "col", "index": "A"}},
            {"type": "COMPARE", "op": "fewer", "left": {"kind": "corners"}, "right": {"kind": "row", "index": 2}},
            {"type": "COMPARE", "op": "equal", "left": {"kind": "row", "index": 3}, "right": {"kind": "col", "index": "C"}},
            {"type": "CONNECTED", "region": {"kind": "row", "index": 2}, "who": "innocent"},
            {"type": "CONNECTED", "region": {"kind": "col", "index": "B"}},
            {"type": "IMPLIES", "if": {"cell": "A1", "status": "criminal"}, "then": {"cell": "C3", "status": "innocent"}},
        ]
        for kind in ("EXACTLY", "AT_LEAST", "AT_MOST"):
            for k in range(0, 9):
                for who in ("criminal", "innocent"):
                    templates.append({"type": kind, "k": k, "region": nb, "who": who})
        for data in templates:
            self._check(b, parse_clue(b, data, "A1"), all_assignments)

    def test_large_cardinality_uses_aux_vars(self):
        b = Board(5)
        varmap = VarMap(b)
        cnf = CNF(varmap.num_primary)
        clue = parse_clue(b, {"type": "EXACTLY", "k": 12, "region": {"kind": "all"}}, "A1")
        ClueEncoder(varmap, "auto").encode(cnf, clue)
        self.assertGreater(cnf.num_aux, 0)
        self.assertLess(len(cnf.clauses), 5000)
        rng = random.Random(3)
        samples = [dict(zip(b.cells, (rng.random() < 0.5 for _ in b.cells))) for _ in range(150)]
        samples += [dict(zip(b.cells, [True] * 12 + [False] * 13))]
        self._check(b, clue, samples, modes=("auto",))

    def test_direct_encoding_clause_counts(self):
        # AT_MOST 1 of 3 -> C(3,2) = 3 binary clauses; AT_LEAST 1 of 3 -> one clause
        cnf = CNF(3)
        encode_at_most(cnf, [1, 2, 3], 1, "direct")
        self.assertEqual(sorted(map(sorted, cnf.clauses)), [[-3, -2], [-3, -1], [-2, -1]])
        cnf = CNF(3)
        encode_at_least(cnf, [1, 2, 3], 1, "direct")
        self.assertEqual(cnf.clauses, [[1, 2, 3]])


class DPLLTests(unittest.TestCase):
    def test_against_brute_force(self):
        rng = random.Random(11)
        for trial in range(400):
            n = rng.randint(1, 9)
            m = rng.randint(1, 4 * n + 2)
            clauses = []
            for _ in range(m):
                width = rng.randint(1, 3)
                clauses.append([rng.choice((1, -1)) * rng.randint(1, n) for _ in range(width)])
            for pure in (False, True):
                res = DPLLSolver(n, clauses, pure_literals=pure).solve()
                self.assertEqual(res.sat, brute_sat(n, clauses), clauses)
                if res.sat:
                    self.assertTrue(satisfies(res.model, clauses))
            assume = [rng.choice((1, -1)) * rng.randint(1, n)]
            res = DPLLSolver(n, clauses).solve(assume)
            self.assertEqual(res.sat, brute_sat(n, clauses + [assume]))

    def test_empty_clause_and_stats(self):
        self.assertFalse(DPLLSolver(2, [[1], []]).solve().sat)
        res = DPLLSolver(3, [[1, 2], [-1, 2], [-2, 3]]).solve([-3])
        self.assertFalse(res.sat)
        self.assertGreater(res.stats.propagations, 0)
        res = DPLLSolver(3, [[1, 2, 3]]).solve()
        self.assertTrue(res.sat)
        self.assertEqual(len(res.model), 4)

    def test_deterministic(self):
        clauses = [[1, 2, -3], [-1, 3], [2, 3], [-2, -3, 4]]
        a = DPLLSolver(4, clauses).solve()
        b = DPLLSolver(4, clauses).solve()
        self.assertEqual(a.model, b.model)
        self.assertEqual(a.stats.decisions, b.stats.decisions)

    def test_assignment_example_from_spec(self):
        # KB = (A v B) & (-A v B): B is entailed, A is unknown.
        solver = DPLLSolver(2, [[1, 2], [-1, 2]])
        self.assertTrue(solver.solve().sat)
        self.assertFalse(solver.solve([-2]).sat)
        self.assertTrue(solver.solve([1]).sat and solver.solve([-1]).sat)


def bundled_puzzles():
    return [Puzzle.load(p) for p in sorted(PUZZLE_DIR.glob("*.json"))]


class AgentTests(unittest.TestCase):
    def test_strategies_agree(self):
        rng = random.Random(5)
        for size in (3, 4):
            for seed in range(4):
                puzzle = generate(size, seed=100 + seed)
                engine = GameEngine(puzzle)
                # random public states along a correct play
                order = [c for c in puzzle.board.cells if c not in puzzle.initial]
                rng.shuffle(order)
                for cut in range(0, len(order), 2):
                    verdicts = {c: puzzle.solution[c] for c in list(puzzle.initial) + order[:cut]}
                    engine.verdicts = dict(verdicts)
                    engine.revealed = list(verdicts)
                    engine.version += 1
                    state = engine.public_state()
                    a = analyze(state, "naive")
                    b = analyze(state, "filter")
                    self.assertEqual(a.classification, b.classification)
                    self.assertLessEqual(b.sat_calls, a.sat_calls)
                    for cell, verdict in a.forced:
                        self.assertEqual(verdict == "CRIMINAL", puzzle.solution[cell])

    def test_bundled_puzzles_solve_without_guessing(self):
        puzzles = bundled_puzzles()
        self.assertGreater(len(puzzles), 0, "no bundled puzzles found")
        for puzzle in puzzles:
            expected = puzzle.meta.get("expected", "SOLVED")
            engine = GameEngine(puzzle)
            report = LogicAgent().solve(engine.player_view())
            self.assertEqual(report.outcome, expected, puzzle.puzzle_id)
            for entry in report.trace:
                if entry.cell:
                    self.assertEqual(entry.verdict == "CRIMINAL", puzzle.solution[entry.cell])
            if expected == "SOLVED":
                self.assertEqual(engine.verdicts, puzzle.solution)
                self.assertTrue(engine.uniqueness().unique, puzzle.puzzle_id)
                if puzzle.board.size <= 4:
                    self.assertEqual(len(puzzle.brute_force_solutions(2)), 1, puzzle.puzzle_id)

    def test_engine_rejections(self):
        puzzle = generate(3, seed=42)
        engine = GameEngine(puzzle, sudden_death=False)
        analysis = engine.analysis()
        cell, verdict = analysis.forced[0]
        wrong = "INNOCENT" if verdict == "CRIMINAL" else "CRIMINAL"
        before = (dict(engine.verdicts), list(engine.revealed))
        self.assertEqual(engine.submit(cell, wrong).status, CONTRADICTED)
        self.assertEqual((engine.verdicts, engine.revealed), before)
        unknown = [c for c, v in analysis.classification.items() if v == "UNKNOWN"]
        if unknown:
            self.assertEqual(engine.submit(unknown[0], "CRIMINAL").status, NOT_PROVABLE)
            self.assertEqual((engine.verdicts, engine.revealed), before)
        res = engine.submit(cell, verdict)
        self.assertEqual(res.status, ACCEPTED)
        self.assertIs(res.revealed_clue, puzzle.clues[cell])
        self.assertEqual(engine.submit(cell, verdict).status, ALREADY_KNOWN)
        self.assertEqual(engine.mistakes, 2 if unknown else 1)

    def test_contradicted_verdict_ends_the_game(self):
        puzzle = generate(3, seed=42)
        engine = GameEngine(puzzle)
        analysis = engine.analysis()
        unknown = [c for c, v in analysis.classification.items() if v == "UNKNOWN"]
        if unknown:  # a guess is only a warning
            self.assertEqual(engine.submit(unknown[0], "CRIMINAL").status, NOT_PROVABLE)
            self.assertEqual(engine.status, "PLAYING")
        cell, verdict = analysis.forced[0]
        before = (dict(engine.verdicts), list(engine.revealed))
        wrong = "INNOCENT" if verdict == "CRIMINAL" else "CRIMINAL"
        self.assertEqual(engine.submit(cell, wrong).status, CONTRADICTED)
        self.assertEqual(engine.status, "LOST")
        self.assertEqual((engine.verdicts, engine.revealed), before)  # nothing revealed
        self.assertEqual(engine.submit(cell, verdict).status, "GAME_OVER")
        engine.reset()
        self.assertEqual(engine.status, "PLAYING")
        self.assertEqual(engine.submit(cell, verdict).status, ACCEPTED)
        engine.reset()
        self.assertEqual(set(engine.verdicts), set(puzzle.initial))

    def test_public_state_hides_secrets(self):
        puzzle = generate(4, seed=9)
        state = GameEngine(puzzle).public_state()
        self.assertEqual(set(state.verdicts), set(puzzle.initial))
        self.assertEqual({c.clue_id for c in state.revealed_clues},
                         {c for c in puzzle.initial if puzzle.clues[c] is not None})
        self.assertFalse(hasattr(state, "solution"))

    def test_hint_support_is_minimal(self):
        puzzle = generate(4, seed=21)
        engine = GameEngine(puzzle)
        agent = LogicAgent()
        for _ in range(5):
            state = engine.public_state()
            hint = agent.hint(state)
            if hint["status"] != "HINT":
                break
            crim = hint["verdict"] == "CRIMINAL"
            support = [c for c in state.revealed_clues if c.clue_id in hint["support"]]
            self.assertTrue(is_entailed(state.board, support, state.verdicts, hint["cell"], crim))
            for i in range(len(support)):
                rest = support[:i] + support[i + 1:]
                self.assertFalse(is_entailed(state.board, rest, state.verdicts, hint["cell"], crim))
            self.assertEqual(minimal_support(state, hint["cell"], crim), hint["support"])
            agent.step(engine.player_view())

    def test_ambiguous_and_inconsistent(self):
        b = Board(2)
        clue = parse_clue(b, {"type": "EXACTLY", "k": 1, "region": {"kind": "row", "index": 1}}, "A2")
        res = check_uniqueness(b, [clue])
        self.assertEqual(res.verdict, "MULTIPLE")
        state = PublicState.make(2, [], [clue], {"A2": False})
        analysis = analyze(state)
        self.assertEqual(analysis.classification["A1"], "UNKNOWN")
        bad = parse_clue(b, {"type": "FACT", "cell": "A2", "status": "criminal"}, "B2")
        self.assertFalse(analyze(PublicState.make(2, [], [bad], {"A2": False})).consistent)

    def test_puzzle_file_validation(self):
        good = generate(3, seed=1).to_dict()
        Puzzle.from_dict(json.loads(json.dumps(good)))
        broken = json.loads(json.dumps(good))
        broken["characters"][0]["status"] = "innocent" if broken["characters"][0]["status"] == "criminal" else "criminal"
        try:
            Puzzle.from_dict(broken)  # may still be consistent if the flip does not falsify any clue
        except PuzzleError:
            pass
        missing = json.loads(json.dumps(good))
        missing["characters"].pop()
        with self.assertRaises(PuzzleError):
            Puzzle.from_dict(missing)
        no_initial = json.loads(json.dumps(good))
        no_initial["initial"] = []
        with self.assertRaises(PuzzleError):
            Puzzle.from_dict(no_initial)


class RobustnessTests(unittest.TestCase):
    def test_cell_ids_must_match_exactly(self):
        board = Board(3)
        for bad in ("A1\n", " A1", "A01", "a1", "D1", "A4"):
            self.assertFalse(board.is_cell(bad), repr(bad))
        with self.assertRaises(ClueError):
            parse_clue(board, {"type": "FACT", "cell": "B1\n", "status": "criminal"})

    def test_malformed_region_values_are_region_errors(self):
        board = Board(3)
        for spec in ({"kind": "ray", "of": "B2", "dir": ["left"]}, {"kind": "row", "index": [1]},
                     {"kind": "neighbors", "of": {"x": 1}}, {"kind": "cells", "cells": [["A1"]]}):
            with self.assertRaises(RegionError, msg=spec):
                resolve_region(board, spec)

    def test_names_must_be_alphabetical(self):
        data = json.loads((PUZZLE_DIR / "01-3x3-a.json").read_text(encoding="utf-8"))
        data["characters"][0]["name"], data["characters"][1]["name"] = \
            data["characters"][1]["name"], data["characters"][0]["name"]
        with self.assertRaises(PuzzleError):
            Puzzle.from_dict(data)

    def test_accented_names_sort_like_plain_letters(self):
        self.assertEqual(sorted(["Zoe", "Émile", "Bo", "Abel"], key=name_key), ["Abel", "Bo", "Émile", "Zoe"])
        self.assertEqual(sorted(["Yamal", "Ødegaard", "Vinícius", "Văn Hậu"], key=name_key),
                         ["Ødegaard", "Văn Hậu", "Vinícius", "Yamal"])
        chars = [{"cell": c, "name": n, "profession": "", "status": "innocent", "clue": None}
                 for c, n in zip(["A1", "B1", "A2", "B2"], ["Abel", "Bo", "Émile", "Zoe"])]
        Puzzle.from_dict({"size": 2, "initial": ["A1"], "characters": chars})  # accepted
        unnamed = [{k: v for k, v in ch.items() if k != "name"} for ch in chars]
        Puzzle.from_dict({"size": 2, "initial": ["A1"], "characters": unnamed})  # names default to cell ids

    def test_step_limit_reached_exactly_on_the_solving_step(self):
        engine = GameEngine(Puzzle.load(PUZZLE_DIR / "01-3x3-a.json"))
        full = LogicAgent().solve(GameEngine(Puzzle.load(PUZZLE_DIR / "01-3x3-a.json")).player_view())
        report = LogicAgent().solve(engine.player_view(), max_steps=full.steps)
        self.assertEqual(report.outcome, SOLVED)

    def test_config_change_charges_the_fresh_analysis(self):
        engine = GameEngine(Puzzle.load(PUZZLE_DIR / "05-4x4-a.json"))
        unknown = next(c for c in engine.board.cells if c not in engine.verdicts)
        engine.submit(unknown, "CRIMINAL")
        before = engine.sat_calls
        engine.submit(unknown, "CRIMINAL")
        self.assertEqual(engine.sat_calls, before)  # same KB version: not charged twice
        engine.cardinality = "counter"
        engine.invalidate()
        engine.submit(unknown, "CRIMINAL")
        self.assertGreater(engine.sat_calls, before)

    def test_solved_game_adds_no_phantom_step(self):
        engine = GameEngine(Puzzle.load(PUZZLE_DIR / "01-3x3-a.json"))
        report = LogicAgent().solve(engine.player_view())
        self.assertEqual(report.outcome, SOLVED)
        self.assertEqual(report.steps, len(report.trace))
        self.assertTrue(all(t.result == ACCEPTED for t in report.trace))


class ThemeTests(unittest.TestCase):
    def test_casts_are_complete_and_distinct(self):
        for theme in THEMES.values():
            if not theme.cast:
                continue
            names = [p.name for p in theme.cast]
            self.assertGreaterEqual(len(names), 16, theme.theme_id)  # at least a 4x4 board
            self.assertEqual(len(set(names)), len(names))
            specs = {json.dumps(p.avatar, sort_keys=True) for p in theme.cast}
            self.assertEqual(len(specs), len(names), "every character has its own avatar")

    def test_theme_is_cosmetic(self):
        for path in sorted(PUZZLE_DIR.glob("0*.json")):
            puzzle = Puzzle.load(path)
            base = GameEngine(puzzle)
            plain = LogicAgent().solve(base.player_view())
            for theme_id in THEMES:
                if 0 < len(THEMES[theme_id].cast) < puzzle.board.size ** 2:
                    continue  # board larger than the cast: the server keeps the file's own names
                skinned = Puzzle.load(path)
                skinned.characters = themed_characters(skinned, skinned.characters, theme_id)
                names = [skinned.characters[c].name for c in skinned.board.cells]
                self.assertEqual(names, sorted(names, key=name_key), (path.name, theme_id))
                self.assertEqual(themed_characters(skinned, skinned.characters, theme_id), skinned.characters)
                report = LogicAgent().solve(GameEngine(skinned).player_view())
                self.assertEqual([(t.cell, t.verdict) for t in report.trace],
                                 [(t.cell, t.verdict) for t in plain.trace], (path.name, theme_id))


if __name__ == "__main__":
    unittest.main()
