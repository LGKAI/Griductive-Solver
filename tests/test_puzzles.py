from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from core.engine import GameEngine
from core.puzzle_generator import generate_puzzle
from core.puzzle_io import dict_to_puzzle, load_puzzle_from_json, puzzle_to_dict, save_puzzle_to_json


class TestPuzzles(unittest.TestCase):
    def test_puzzle_sizes_and_uniqueness(self) -> None:
        """Verify that generated puzzles across dimensions have unique solutions."""
        for r, c in ((3, 3), (3, 4), (4, 4), (5, 5)):
            puzzle = generate_puzzle(seed=5000 + r * 10 + c, rows=r, columns=c)
            engine = GameEngine(puzzle)
            is_unique, stats = engine.uniqueness_check()
            self.assertTrue(is_unique, f"Puzzle {r}x{c} must have a unique satisfying model.")

    def test_json_serialization(self) -> None:
        """Test round-trip JSON serialization and deserialization."""
        puzzle = generate_puzzle(seed=4321, rows=3, columns=3)
        data = puzzle_to_dict(puzzle)
        restored = dict_to_puzzle(data)

        self.assertEqual(puzzle.id, restored.id)
        self.assertEqual(puzzle.rows, restored.rows)
        self.assertEqual(puzzle.columns, restored.columns)
        self.assertEqual(puzzle.solution, restored.solution)
        self.assertEqual(len(puzzle.clues), len(restored.clues))

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "test_case.json"
            save_puzzle_to_json(puzzle, tmp_path)
            loaded = load_puzzle_from_json(tmp_path)
            self.assertEqual(puzzle.id, loaded.id)
            self.assertEqual(puzzle.solution, loaded.solution)


if __name__ == "__main__":
    unittest.main()

