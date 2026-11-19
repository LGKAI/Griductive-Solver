"""Entailment classification, hint explanations and uniqueness checking.

For an unsolved character i at step t::

    KB_t |= C_i   <=>  KB_t AND NOT C_i  is UNSAT   ->  CRIMINAL
    KB_t |= -C_i  <=>  KB_t AND C_i      is UNSAT   ->  INNOCENT
    both satisfiable                               ->  UNKNOWN
    KB_t itself unsatisfiable                      ->  INCONSISTENT

Two query strategies give identical classifications:

* ``naive``  - two SAT calls per unknown character.
* ``filter`` - model filtering: solve KB_t once to get a model M; for each
  unknown i ask only ``KB_t AND (C_i != M_i)``. If UNSAT the verdict is M_i.
  If SAT, the new model M' shows that every j with M'_j != M_j is UNKNOWN,
  so those characters need no query of their own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

from .board import Board
from .clues import Clue
from .dpll import DPLLSolver, SolverStats
from .knowledge import KnowledgeBase, PublicState, build_kb, build_public_kb

CRIMINAL_V = "CRIMINAL"
INNOCENT_V = "INNOCENT"
UNKNOWN_V = "UNKNOWN"
INCONSISTENT_V = "INCONSISTENT"

STRATEGIES = ("filter", "naive")


@dataclass
class SatQuery:
    label: str  # e.g. "KB ∧ ¬C(B2)"
    cell: Optional[str]
    assumed_criminal: Optional[bool]
    result: str  # SAT / UNSAT
    stats: dict

    def to_dict(self) -> dict:
        return {"query": self.label, "cell": self.cell, "assumed_criminal": self.assumed_criminal,
                "result": self.result, **self.stats}


@dataclass
class Analysis:
    consistent: bool
    classification: dict[str, str]  # unknown cell -> CRIMINAL / INNOCENT / UNKNOWN
    queries: list[SatQuery]
    kb_stats: dict
    solver: SolverStats = field(default_factory=SolverStats)

    @property
    def forced(self) -> list[tuple[str, str]]:
        """Forced (cell, verdict) pairs, in row-major order."""
        return [(c, v) for c, v in self.classification.items() if v in (CRIMINAL_V, INNOCENT_V)]

    @property
    def sat_calls(self) -> int:
        return len(self.queries)


def _query_label(cell: str, criminal: bool) -> str:
    return f"KB ∧ {'' if criminal else '¬'}C({cell})"


def analyze(state: PublicState, strategy: str = "filter", cardinality: str = "auto",
            time_limit: Optional[float] = None) -> Analysis:
    """Classify every unresolved character of a public state."""
    kb = build_public_kb(state, cardinality)
    return analyze_kb(kb, state.unknown_cells, strategy, time_limit)


def analyze_kb(kb: KnowledgeBase, cells: Iterable[str], strategy: str = "filter",
               time_limit: Optional[float] = None) -> Analysis:
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}")
    cells = list(cells)
    solver = DPLLSolver(kb.cnf.num_vars, kb.cnf.clauses)
    total = SolverStats()
    queries: list[SatQuery] = []

    def run(label: str, cell: Optional[str], assume: Optional[bool]):
        assumptions = [] if cell is None else [kb.varmap.var(cell) if assume else -kb.varmap.var(cell)]
        res = solver.solve(assumptions, time_limit)
        total.add(res.stats)
        queries.append(SatQuery(label, cell, assume, res.status, res.stats.to_dict()))
        return res

    base = run("KB", None, None)
    if not base.sat:
        return Analysis(False, {c: INCONSISTENT_V for c in cells}, queries, kb.stats, total)

    classification: dict[str, str] = {}
    if strategy == "naive":
        for cell in cells:
            can_be_innocent = run(_query_label(cell, False), cell, False).sat
            can_be_criminal = run(_query_label(cell, True), cell, True).sat
            classification[cell] = _verdict(can_be_criminal, can_be_innocent)
        return Analysis(True, classification, queries, kb.stats, total)

    model = base.model
    var = kb.varmap.var
    unknown: set[str] = set()
    for cell in cells:
        if cell in unknown:
            classification[cell] = UNKNOWN_V
            continue
        value = model[var(cell)]
        res = run(_query_label(cell, not value), cell, not value)
        if not res.sat:
            classification[cell] = CRIMINAL_V if value else INNOCENT_V
        else:
            classification[cell] = UNKNOWN_V
            for other in cells:
                if res.model[var(other)] != model[var(other)]:
                    unknown.add(other)
    return Analysis(True, classification, queries, kb.stats, total)


def _verdict(can_be_criminal: bool, can_be_innocent: bool) -> str:
    if can_be_criminal and can_be_innocent:
        return UNKNOWN_V
    if can_be_criminal:
        return CRIMINAL_V
    if can_be_innocent:
        return INNOCENT_V
    return INCONSISTENT_V


def is_entailed(board: Board, clues: Iterable[Clue], verdicts: Mapping[str, bool], cell: str,
                criminal: bool, cardinality: str = "auto") -> bool:
    """True iff clues + verdicts entail the given status for ``cell``."""
    kb = build_kb(board, clues, verdicts, cardinality)
    lit = kb.varmap.var(cell)
    return not DPLLSolver(kb.cnf.num_vars, kb.cnf.clauses).solve([-lit if criminal else lit]).sat


def minimal_support(state: PublicState, cell: str, criminal: bool, cardinality: str = "auto") -> list[str]:
    """A subset-minimal set of revealed clue ids that, together with the proved
    verdicts, still entails ``cell``'s status (deletion-based core extraction)."""
    support = list(state.revealed_clues)
    if not is_entailed(state.board, support, state.verdicts, cell, criminal, cardinality):
        return []
    i = 0
    while i < len(support):
        trial = support[:i] + support[i + 1:]
        if is_entailed(state.board, trial, state.verdicts, cell, criminal, cardinality):
            support = trial
        else:
            i += 1
    return [c.clue_id for c in support]


# ------------------------------------------------------------ uniqueness
@dataclass
class UniquenessResult:
    count: int  # number of solutions found, capped at ``limit``
    solutions: list[dict[str, bool]]
    sat_calls: int
    stats: SolverStats

    @property
    def unique(self) -> bool:
        return self.count == 1

    @property
    def verdict(self) -> str:
        if self.count == 0:
            return "NO_SOLUTION"
        return "UNIQUE" if self.count == 1 else "MULTIPLE"


def check_uniqueness(board: Board, clues: Iterable[Clue], verdicts: Mapping[str, bool] | None = None,
                     limit: int = 2, cardinality: str = "auto",
                     time_limit: Optional[float] = None) -> UniquenessResult:
    """Count solutions of the complete clue set (up to ``limit``) with blocking clauses.

    Each found model is blocked on the primary variables only, so different
    auxiliary values never count as different solutions.
    """
    kb = build_kb(board, clues, verdicts or {}, cardinality)
    clauses = [list(c) for c in kb.cnf.clauses]
    total = SolverStats()
    solutions: list[dict[str, bool]] = []
    calls = 0
    while len(solutions) < limit:
        res = DPLLSolver(kb.cnf.num_vars, clauses).solve(time_limit=time_limit)
        calls += 1
        total.add(res.stats)
        if not res.sat:
            break
        sol = {cell: res.model[kb.varmap.var(cell)] for cell in board.cells}
        solutions.append(sol)
        clauses.append([-kb.varmap.var(c) if v else kb.varmap.var(c) for c, v in sol.items()])
    return UniquenessResult(len(solutions), solutions, calls, total)
