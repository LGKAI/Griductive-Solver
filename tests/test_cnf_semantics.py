from __future__ import annotations

from itertools import product
import unittest

from core.clues import evaluate_clue
from core.cnf import CNFEncoder
from core.models import Character, Clue, ClueKind, Status


class TestCNFSemanticsEquivalence(unittest.TestCase):
    """Exhaustively verify that the direct semantic evaluator matches
    CNF clause truth satisfaction for all supported clue templates."""

    def setUp(self) -> None:
        self.characters = (
            Character("A1", "Ada", "Detective"),
            Character("B1", "Binh", "Doctor"),
            Character("C1", "Chi", "Chef"),
            Character("A2", "Duy", "Engineer"),
        )
        self.encoder = CNFEncoder(self.characters)

    def _verify_clue(self, clue: Clue, ref_cells: tuple[str, ...]) -> None:
        clauses = self.encoder.encode_clue(clue)
        rev_map = self.encoder.reverse_map

        for combo in product((False, True), repeat=len(ref_cells)):
            assignment = {cell: Status.from_boolean(val) for cell, val in zip(ref_cells, combo)}
            # Semantic evaluator result
            sem_val = evaluate_clue(clue, assignment)

            # CNF clauses evaluation
            cnf_val = all(
                any(
                    assignment[rev_map[abs(lit)]].boolean == (lit > 0)
                    for lit in clause
                    if abs(lit) in rev_map and rev_map[abs(lit)] in assignment
                )
                for clause in clauses
            )
            self.assertEqual(
                sem_val,
                cnf_val,
                f"Mismatch for clue {clue.kind} on assignment {combo}: sem={sem_val}, cnf={cnf_val}",
            )

    def test_fact_semantics(self) -> None:
        clue = Clue("C1", "A1", ClueKind.FACT, targets=("B1",), status=Status.CRIMINAL)
        self._verify_clue(clue, ("B1",))

    def test_same_semantics(self) -> None:
        clue = Clue("C2", "A1", ClueKind.SAME, targets=("A1", "B1"))
        self._verify_clue(clue, ("A1", "B1"))

    def test_different_semantics(self) -> None:
        clue = Clue("C3", "A1", ClueKind.DIFFERENT, targets=("A1", "B1"))
        self._verify_clue(clue, ("A1", "B1"))

    def test_exactly_semantics(self) -> None:
        clue = Clue("C4", "A1", ClueKind.EXACTLY, region=("A1", "B1", "C1"), k=2)
        self._verify_clue(clue, ("A1", "B1", "C1"))

    def test_at_least_semantics(self) -> None:
        clue = Clue("C5", "A1", ClueKind.AT_LEAST, region=("A1", "B1", "C1"), k=2)
        self._verify_clue(clue, ("A1", "B1", "C1"))

    def test_at_most_semantics(self) -> None:
        clue = Clue("C6", "A1", ClueKind.AT_MOST, region=("A1", "B1", "C1"), k=1)
        self._verify_clue(clue, ("A1", "B1", "C1"))

    def test_parity_semantics(self) -> None:
        clue_even = Clue("C7", "A1", ClueKind.PARITY, region=("A1", "B1", "C1"), parity="EVEN")
        self._verify_clue(clue_even, ("A1", "B1", "C1"))
        clue_odd = Clue("C8", "A1", ClueKind.PARITY, region=("A1", "B1", "C1"), parity="ODD")
        self._verify_clue(clue_odd, ("A1", "B1", "C1"))

    def test_count_compare_semantics(self) -> None:
        clue = Clue("C9", "A1", ClueKind.COUNT_COMPARE, region=("A1", "B1"), region_b=("C1", "A2"), comparison="GT")
        self._verify_clue(clue, ("A1", "B1", "C1", "A2"))


if __name__ == "__main__":
    unittest.main()

