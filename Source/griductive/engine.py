"""Game Engine: owns the complete puzzle, the hidden solution and unrevealed clues.

The engine exposes only a :class:`PublicState` snapshot to players and
agents. A verdict is accepted only when it is entailed by the *public*
knowledge base; the hidden solution is used as a final sanity check and to
reveal the next clue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .clues import Clue
from .entailment import (CRIMINAL_V, INNOCENT_V, Analysis, UniquenessResult, analyze,
                         check_uniqueness)
from .knowledge import PublicCharacter, PublicState
from .puzzle import Puzzle

ACCEPTED = "ACCEPTED"
NOT_PROVABLE = "NOT_PROVABLE"
CONTRADICTED = "CONTRADICTED"
ALREADY_KNOWN = "ALREADY_KNOWN"
INVALID = "INVALID"
INCONSISTENT = "INCONSISTENT"
GAME_OVER = "GAME_OVER"

PLAYING = "PLAYING"
SOLVED = "SOLVED"
LOST = "LOST"  # a CONTRADICTED verdict ended the game (sudden death)


class PuzzleIntegrityError(RuntimeError):
    """An entailed verdict disagrees with the stored solution (corrupt puzzle)."""


@dataclass
class SubmitResult:
    status: str
    cell: str
    verdict: str
    message: str
    revealed_clue: Optional[Clue] = None

    @property
    def accepted(self) -> bool:
        return self.status == ACCEPTED


@dataclass
class GameEngine:
    puzzle: Puzzle
    strategy: str = "filter"
    cardinality: str = "auto"
    verdicts: dict[str, bool] = field(default_factory=dict)
    revealed: list[str] = field(default_factory=list)  # cells whose clue is face-up
    mistakes: int = 0
    sudden_death: bool = True  # a CONTRADICTED verdict ends the game
    lost: Optional[tuple[str, str]] = None  # (cell, verdict) of the verdict that ended the game
    version: int = 0
    sat_calls: int = 0  # SAT calls the engine itself used to judge verdicts
    _cache: Optional[tuple[int, Analysis]] = field(default=None, repr=False)
    _charged: Optional[int] = field(default=None, repr=False)  # version whose analysis is in sat_calls

    def __post_init__(self) -> None:
        self.reset()

    # ------------------------------------------------------------ state
    def reset(self) -> None:
        self.verdicts = {c: self.puzzle.solution[c] for c in self.puzzle.initial}
        self.revealed = list(self.puzzle.initial)
        self.mistakes = 0
        self.lost = None
        self.sat_calls = 0
        self.version += 1
        self._cache = None
        self._charged = None

    @property
    def board(self):
        return self.puzzle.board

    @property
    def status(self) -> str:
        if self.lost is not None:
            return LOST
        return SOLVED if len(self.verdicts) == len(self.board.cells) else PLAYING

    def public_state(self) -> PublicState:
        chars = tuple(PublicCharacter(c, ch.name, ch.profession) for c, ch in self.puzzle.characters.items())
        clues = [self.puzzle.clues[c] for c in self.revealed if self.puzzle.clues[c] is not None]
        return PublicState.make(self.board.size, chars, clues, self.verdicts, self.version)

    def analysis(self) -> Analysis:
        """Entailment analysis of the current public state (cached per version)."""
        if self._cache is None or self._cache[0] != self.version:
            self._cache = (self.version, analyze(self.public_state(), self.strategy, self.cardinality))
        return self._cache[1]

    def player_view(self) -> "PlayerView":
        """The only handle given to players and agents (no access to the puzzle)."""
        return PlayerView(self)

    # ---------------------------------------------------------- actions
    def submit(self, cell: str, verdict: str) -> SubmitResult:
        verdict = str(verdict).upper()
        if not self.board.is_cell(cell) or verdict not in (CRIMINAL_V, INNOCENT_V):
            return SubmitResult(INVALID, str(cell), verdict, "Unknown cell or verdict.")
        if self.lost is not None:
            return SubmitResult(GAME_OVER, cell, verdict, "The game is over. Restart the case to play again.")
        if cell in self.verdicts:
            return SubmitResult(ALREADY_KNOWN, cell, verdict, "This character is already solved.")
        analysis = self.analysis()
        if self._charged != self.version:
            # ``sat_calls`` counts the analysis used to judge verdicts, once per
            # knowledge-base version (views of the state are not charged).
            self.sat_calls += analysis.sat_calls
            self._charged = self.version
        if not analysis.consistent:
            return SubmitResult(INCONSISTENT, cell, verdict, "The public clues contradict each other.")
        forced = analysis.classification[cell]
        name = self.puzzle.characters[cell].name
        if forced == verdict:
            if self.puzzle.solution[cell] != (verdict == CRIMINAL_V):
                raise PuzzleIntegrityError(f"{cell}: entailed verdict {verdict} contradicts the stored solution")
            self.verdicts[cell] = verdict == CRIMINAL_V
            self.revealed.append(cell)
            self.version += 1
            return SubmitResult(ACCEPTED, cell, verdict, f"Correct: {name} is {verdict.lower()}.",
                                self.puzzle.clues[cell])
        self.mistakes += 1
        if forced in (CRIMINAL_V, INNOCENT_V):
            # The knowledge base is untouched (nothing is revealed); with sudden death the
            # game simply stops accepting verdicts until it is restarted.
            if self.sudden_death:
                self.lost = (cell, verdict)
            return SubmitResult(CONTRADICTED, cell, verdict,
                                f"Contradicted: the clues prove {name} is {forced.lower()}.")
        return SubmitResult(NOT_PROVABLE, cell, verdict,
                            f"Not provable yet: {name} could still be either. No guessing!")

    def invalidate(self) -> None:
        """Drop the cached analysis (e.g. after a configuration change)."""
        self._cache = None
        self._charged = None  # the fresh analysis will be charged at the next submit

    def uniqueness(self, time_limit: Optional[float] = None) -> UniquenessResult:
        """Uniqueness of the complete clue set plus the initially known statuses."""
        clues = [c for c in self.puzzle.clues.values() if c is not None]
        initial = {c: self.puzzle.solution[c] for c in self.puzzle.initial}
        return check_uniqueness(self.board, clues, initial, limit=2, cardinality=self.cardinality,
                                time_limit=time_limit)


class PlayerView:
    """Facade handed to the Logic Agent: ``public_state()`` and ``submit()`` only.

    The engine reference is name-mangled so that agent code cannot reach the
    puzzle (hidden statuses, unrevealed clues) through this object by accident.
    """

    __slots__ = ("__engine",)

    def __init__(self, engine: GameEngine):
        self.__engine = engine

    def public_state(self) -> PublicState:
        return self.__engine.public_state()

    def submit(self, cell: str, verdict: str) -> SubmitResult:
        return self.__engine.submit(cell, verdict)
