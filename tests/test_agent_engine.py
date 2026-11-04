from __future__ import annotations

import unittest

from core.agent import LogicAgent
from core.engine import GameEngine
from core.models import Status, SubmissionResult, Verdict
from core.puzzle_generator import generate_puzzle


class TestAgentEngineInteraction(unittest.TestCase):
    def setUp(self) -> None:
        self.puzzle = generate_puzzle(seed=3003, rows=3, columns=3)
        self.engine = GameEngine(self.puzzle)
        self.agent = LogicAgent()

    def test_public_state_privacy(self) -> None:
        """Ensure PublicState contains NO hidden solution or unrevealed clues."""
        state = self.engine.public_state()
        self.assertFalse(hasattr(state, "solution"))
        self.assertEqual(len(state.known_verdicts), len(self.puzzle.initially_revealed))
        self.assertEqual(len(state.revealed_clues), len(self.puzzle.initially_revealed))

    def test_verdict_rejection_leaves_state_unchanged(self) -> None:
        """Submitting an unprovable or contradicted verdict leaves state untouched."""
        state_before = self.engine.public_state()
        unsolved_cells = [c for c in self.puzzle.solution if c not in state_before.known_verdicts]

        target_cell = unsolved_cells[0]
        classification = self.agent.classify_all(state_before)
        target_deduction = classification.verdicts[target_cell]

        if target_deduction.verdict is Verdict.UNKNOWN:
            # Should return NOT_PROVABLE
            res = self.engine.submit(target_cell, Status.CRIMINAL, self.agent)
            self.assertEqual(res, SubmissionResult.NOT_PROVABLE)
            # Ensure card was NOT revealed
            self.assertNotIn(target_cell, self.engine._known)
            self.assertNotIn(target_cell, self.engine._revealed)

    def test_auto_solve_completes_without_guessing(self) -> None:
        """Puzzle should solve 100% deterministically without guessing."""
        while not self.engine.is_solved():
            res, ded = self.engine.auto_step(self.agent)
            self.assertEqual(res, SubmissionResult.ACCEPTED)
            self.assertIn(ded.verdict, (Verdict.CRIMINAL, Verdict.INNOCENT))

        self.assertTrue(self.engine.is_solved())
        self.assertEqual(len(self.engine._known), self.puzzle.cell_count)


if __name__ == "__main__":
    unittest.main()

