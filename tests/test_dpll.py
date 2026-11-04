from __future__ import annotations

import unittest
from core.dpll import DPLLSolver


class TestDPLLSolver(unittest.TestCase):
    def setUp(self) -> None:
        self.solver = DPLLSolver()

    def test_simple_sat(self) -> None:
        # (x1 or x2) and (~x1 or x2) -> SAT with x2 = True
        clauses = ((1, 2), (-1, 2))
        res = self.solver.solve(clauses, variable_count=2)
        self.assertTrue(res.satisfiable)
        self.assertIsNotNone(res.assignment)
        self.assertTrue(res.assignment[2])

    def test_simple_unsat(self) -> None:
        # (x1) and (~x1) -> UNSAT
        clauses = ((1,), (-1,))
        res = self.solver.solve(clauses, variable_count=1)
        self.assertFalse(res.satisfiable)
        self.assertIsNone(res.assignment)

    def test_assumptions_contradiction(self) -> None:
        # (x1 or x2) under assumptions [x1, -x1] -> immediate contradiction
        clauses = ((1, 2),)
        res = self.solver.solve(clauses, variable_count=2, assumptions=(1, -1))
        self.assertFalse(res.satisfiable)

    def test_unit_propagation_chain(self) -> None:
        # x1, (~x1 or x2), (~x2 or x3) -> should propagate x1=True, x2=True, x3=True
        clauses = ((1,), (-1, 2), (-2, 3))
        res = self.solver.solve(clauses, variable_count=3)
        self.assertTrue(res.satisfiable)
        self.assertEqual(res.assignment, {1: True, 2: True, 3: True})
        self.assertGreaterEqual(res.stats.propagations, 2)

    def test_complete_assignment_guarantee(self) -> None:
        # 3 variables, but formula only mentions x1
        clauses = ((1,),)
        res = self.solver.solve(clauses, variable_count=3)
        self.assertTrue(res.satisfiable)
        self.assertEqual(len(res.assignment), 3)
        self.assertTrue(res.assignment[1])


if __name__ == "__main__":
    unittest.main()

