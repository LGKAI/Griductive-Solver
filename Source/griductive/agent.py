"""Deductive Logic Agent built on the DPLL solver.

The agent only reads :class:`PublicState` snapshots and talks to the engine
through ``public_state()`` and ``submit(cell, verdict)``. It never guesses:
it submits a verdict only when that verdict is entailed by the public KB.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Protocol

from .clues import Clue, clue_text
from .dpll import SolverStats, SolverTimeout
from .engine import PuzzleIntegrityError
from .entailment import CRIMINAL_V, INNOCENT_V, UNKNOWN_V, Analysis, analyze, minimal_support
from .knowledge import PublicState

SOLVED = "SOLVED"
STUCK = "STUCK"
INCONSISTENT = "INCONSISTENT"
TIMEOUT = "TIMEOUT"
STEP_LIMIT = "STEP_LIMIT"
REJECTED = "REJECTED"
ERROR = "ERROR"
IN_PROGRESS = "IN_PROGRESS"


class EngineInterface(Protocol):
    def public_state(self) -> PublicState: ...
    def submit(self, cell: str, verdict: str): ...


@dataclass
class TraceEntry:
    step: int
    active_clues: list[str]
    sat_queries: list[dict]
    classification: dict[str, str]
    cell: Optional[str]
    verdict: Optional[str]
    result: str
    revealed_clue: Optional[dict]
    revealed_text: Optional[str]
    kb_stats: dict
    solver: dict
    name: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "active_clues": self.active_clues,
            "sat_calls": len(self.sat_queries),
            "sat_queries": self.sat_queries,
            "classification": self.classification,
            "cell": self.cell,
            "name": self.name,
            "verdict": self.verdict,
            "result": self.result,
            "revealed_clue": self.revealed_clue,
            "revealed_text": self.revealed_text,
            "kb": self.kb_stats,
            "solver": self.solver,
        }


@dataclass
class SolveReport:
    outcome: str
    steps: int
    sat_calls: int
    trace: list[TraceEntry]
    solver: SolverStats
    max_kb: dict
    runtime: float

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "steps": self.steps,
            "sat_calls": self.sat_calls,
            "solver": self.solver.to_dict(),
            "max_kb": self.max_kb,
            "runtime_ms": round(self.runtime * 1000, 2),
            "trace": [t.to_dict() for t in self.trace],
        }


@dataclass
class LogicAgent:
    strategy: str = "filter"
    cardinality: str = "auto"
    time_limit: Optional[float] = None  # per SAT call
    steps_taken: int = 0
    history: list[TraceEntry] = field(default_factory=list)

    # ------------------------------------------------------------ reasoning
    def analyze(self, state: PublicState) -> Analysis:
        return analyze(state, self.strategy, self.cardinality, self.time_limit)

    @staticmethod
    def choose(analysis: Analysis) -> Optional[tuple[str, str]]:
        """First forced verdict in row-major order, or None."""
        forced = analysis.forced
        return forced[0] if forced else None

    def hint(self, state: PublicState) -> dict:
        """Name one provable character and the revealed clues that prove it."""
        analysis = self.analyze(state)
        if not analysis.consistent:
            return {"status": INCONSISTENT, "message": "The revealed clues contradict each other."}
        if not state.unknown_cells:
            return {"status": SOLVED, "message": "Every character is already solved."}
        pick = self.choose(analysis)
        if pick is None:
            return {"status": STUCK, "message": "No character can be proved from the public clues."}
        cell, verdict = pick
        support = minimal_support(state, cell, verdict == CRIMINAL_V, self.cardinality)
        return {
            "status": "HINT",
            "cell": cell,
            "name": state.name(cell),
            "verdict": verdict,
            "support": support,
            "forced_count": len(analysis.forced),
            "message": f"{state.name(cell)} can be proved {verdict.lower()} using clue(s) from "
                       + ", ".join(state.name(c) for c in support) + ".",
        }

    # ------------------------------------------------------------ acting
    def step(self, engine: EngineInterface) -> TraceEntry:
        """Run one deduction step: classify, choose a forced verdict, submit it."""
        state = engine.public_state()
        if not state.unknown_cells:
            # Nothing left to deduce: report SOLVED without counting a deduction step.
            return TraceEntry(step=self.steps_taken, active_clues=list(state.active_clue_ids), sat_queries=[],
                              classification={}, cell=None, verdict=None, result=SOLVED, revealed_clue=None,
                              revealed_text=None, kb_stats={}, solver=SolverStats().to_dict())
        self.steps_taken += 1
        base = dict(step=self.steps_taken, active_clues=list(state.active_clue_ids), revealed_clue=None,
                    revealed_text=None)
        try:
            analysis = self.analyze(state)
        except SolverTimeout:
            entry = TraceEntry(sat_queries=[], classification={}, cell=None, verdict=None, result=TIMEOUT,
                               kb_stats={}, solver=SolverStats().to_dict(), **base)
            self.history.append(entry)
            return entry
        common = dict(sat_queries=[q.to_dict() for q in analysis.queries],
                      classification=dict(analysis.classification),
                      kb_stats=analysis.kb_stats, solver=analysis.solver.to_dict(), **base)
        if not analysis.consistent:
            entry = TraceEntry(cell=None, verdict=None, result=INCONSISTENT, **common)
        else:
            pick = self.choose(analysis)
            if pick is None:
                entry = TraceEntry(cell=None, verdict=None, result=STUCK, **common)
            else:
                cell, verdict = pick
                try:
                    outcome = engine.submit(cell, verdict)
                except PuzzleIntegrityError:
                    entry = TraceEntry(cell=cell, verdict=verdict, name=state.name(cell), result=ERROR, **common)
                    self.history.append(entry)
                    return entry
                clue: Optional[Clue] = outcome.revealed_clue
                entry = TraceEntry(cell=cell, verdict=verdict, name=state.name(cell),
                                   result=outcome.status if outcome.accepted else REJECTED, **common)
                if clue is not None:
                    entry.revealed_clue = {"id": clue.clue_id, **clue.to_dict()}
                    entry.revealed_text = clue_text(clue)
        self.history.append(entry)
        return entry

    def reset(self) -> None:
        self.steps_taken = 0
        self.history.clear()

    def solve(self, engine: EngineInterface, max_steps: int = 1000) -> SolveReport:
        """Repeat :meth:`step` until solved or another terminal state is reached."""
        self.reset()
        start = time.perf_counter()
        trace: list[TraceEntry] = []
        total = SolverStats()
        sat_calls = 0
        max_kb = {"primary_vars": 0, "aux_vars": 0, "clauses": 0}
        outcome = IN_PROGRESS
        for _ in range(max_steps):
            entry = self.step(engine)
            if entry.result == SOLVED:
                outcome = SOLVED
                break
            trace.append(entry)
            sat_calls += len(entry.sat_queries)
            for key, value in entry.solver.items():
                if key == "runtime_ms":
                    total.runtime += value / 1000
                else:
                    setattr(total, key, getattr(total, key) + value)
            for key in max_kb:
                max_kb[key] = max(max_kb[key], entry.kb_stats.get(key, 0))
            if entry.result != "ACCEPTED":
                outcome = entry.result
                break
        else:
            # the last allowed step may itself have solved the puzzle
            outcome = SOLVED if not engine.public_state().unknown_cells else STEP_LIMIT
        steps = sum(1 for t in trace if t.result == "ACCEPTED")
        return SolveReport(outcome, steps, sat_calls, trace, total, max_kb, time.perf_counter() - start)


__all__ = ["LogicAgent", "TraceEntry", "SolveReport", "SOLVED", "STUCK", "INCONSISTENT", "TIMEOUT", "STEP_LIMIT",
           "UNKNOWN_V", "CRIMINAL_V", "INNOCENT_V"]
