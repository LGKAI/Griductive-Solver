"""Test suite for Griductive Solver."""
import sys
from pathlib import Path

# Add Source root to sys.path so tests can import core, gui, etc.
source_root = str(Path(__file__).resolve().parents[1])
if source_root not in sys.path:
    sys.path.insert(0, source_root)
