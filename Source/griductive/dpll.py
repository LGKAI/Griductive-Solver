"""A DPLL SAT solver written from scratch.

Features:

* unit propagation driven by per-literal occurrence lists,
* conflict detection (a clause whose literals are all false),
* deterministic branching (lowest-numbered unassigned variable that occurs in
  a not-yet-satisfied clause; value ``True`` tried first),
* recursive branching with chronological backtracking,
* optional pure-literal elimination at the root,
* assumptions (temporary unit literals) for entailment queries,
* statistics: decisions, propagations, backtracks, conflicts and runtime.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))

SAT = "SAT"
UNSAT = "UNSAT"


class SolverTimeout(RuntimeError):
    """Raised when the solver exceeds its time budget."""


@dataclass
class SolverStats:
    decisions: int = 0
    propagations: int = 0
    backtracks: int = 0
    conflicts: int = 0
    runtime: float = 0.0  # seconds

    def add(self, other: "SolverStats") -> None:
        self.decisions += other.decisions
        self.propagations += other.propagations
        self.backtracks += other.backtracks
        self.conflicts += other.conflicts
        self.runtime += other.runtime

    def to_dict(self) -> dict:
        return {
            "decisions": self.decisions,
            "propagations": self.propagations,
            "backtracks": self.backtracks,
            "conflicts": self.conflicts,
            "runtime_ms": round(self.runtime * 1000, 3),
        }


@dataclass
class SolveResult:
    status: str  # SAT or UNSAT
    model: Optional[list[bool]] = None  # model[v] for v in 1..num_vars (index 0 unused)
    stats: SolverStats = field(default_factory=SolverStats)

    @property
    def sat(self) -> bool:
        return self.status == SAT


class DPLLSolver:
    """Solve a fixed clause set, possibly many times under different assumptions."""

    def __init__(self, num_vars: int, clauses: Iterable[Sequence[int]], pure_literals: bool = False):
        self.num_vars = num_vars
        self.pure_literals = pure_literals
        self.clauses: list[tuple[int, ...]] = []
        self.has_empty = False
        for clause in clauses:
            lits = tuple(dict.fromkeys(clause))
            if any(-l in lits for l in lits):
                continue  # tautology
            for lit in lits:
                if lit == 0 or abs(lit) > num_vars:
                    raise ValueError(f"literal {lit} out of range 1..{num_vars}")
            if not lits:
                self.has_empty = True  # counted as one conflict when solving
            self.clauses.append(lits)
        # occurrence lists indexed by literal + num_vars
        self._occ: list[list[int]] = [[] for _ in range(2 * num_vars + 1)]
        for ci, clause in enumerate(self.clauses):
            for lit in clause:
                self._occ[lit + num_vars].append(ci)
        self._units = [c[0] for c in self.clauses if len(c) == 1]

    # ------------------------------------------------------------ public
    def solve(self, assumptions: Iterable[int] = (), time_limit: Optional[float] = None) -> SolveResult:
        stats = SolverStats()
        start = time.perf_counter()
        self._deadline = None if time_limit is None else start + time_limit
        self._stats = stats
        self._value = [0] * (self.num_vars + 1)  # 0 unassigned, 1 true, -1 false
        self._trail: list[int] = []
        self._qhead = 0
        try:
            ok = not self.has_empty
            if not ok:
                stats.conflicts += 1
            if ok:
                queued = [(lit, False) for lit in assumptions] + [(lit, True) for lit in self._units]
                for lit, implied in queued:
                    if lit == 0 or abs(lit) > self.num_vars:
                        raise ValueError(f"assumption {lit} out of range 1..{self.num_vars}")
                    if not self._enqueue(lit, implied=implied):
                        stats.conflicts += 1  # contradictory assumptions / unit clauses
                        ok = False
                        break
            if ok:
                ok = self._propagate()  # counts its own conflicts
            if ok and self.pure_literals:
                ok = self._eliminate_pure_literals()
            try:
                sat = ok and self._search()
            except RecursionError:
                raise SolverTimeout("DPLL search too deep for the recursion limit") from None
        finally:
            stats.runtime = time.perf_counter() - start
        if not sat:
            return SolveResult(UNSAT, None, stats)
        model = [False] * (self.num_vars + 1)
        for v in range(1, self.num_vars + 1):
            model[v] = self._value[v] == 1  # unassigned vars are free: choose False
        return SolveResult(SAT, model, stats)

    # ---------------------------------------------------------- internals
    def _lit_value(self, lit: int) -> int:
        v = self._value[abs(lit)]
        return v if lit > 0 else -v

    def _enqueue(self, lit: int, implied: bool = False) -> bool:
        current = self._lit_value(lit)
        if current == 1:
            return True
        if current == -1:
            return False
        self._value[abs(lit)] = 1 if lit > 0 else -1
        self._trail.append(lit)
        if implied:
            self._stats.propagations += 1
        return True

    def _propagate(self) -> bool:
        """Unit propagation over the trail. Returns False on conflict."""
        value = self._value
        clauses = self.clauses
        n = self.num_vars
        while self._qhead < len(self._trail):
            lit = self._trail[self._qhead]
            self._qhead += 1
            for ci in self._occ[-lit + n]:  # clauses where ``lit`` became false
                unassigned = 0
                last = 0
                satisfied = False
                for x in clauses[ci]:
                    v = value[x] if x > 0 else -value[-x]
                    if v == 1:
                        satisfied = True
                        break
                    if v == 0:
                        unassigned += 1
                        last = x
                        if unassigned > 1:
                            break
                if satisfied or unassigned > 1:
                    continue
                if unassigned == 0:
                    self._stats.conflicts += 1
                    return False
                self._enqueue(last, implied=True)
        return True

    def _eliminate_pure_literals(self) -> bool:
        """Assign literals that only occur with one polarity in unsatisfied clauses."""
        changed = True
        while changed:
            changed = False
            polarity: dict[int, set[int]] = {}
            for clause in self.clauses:
                if any(self._lit_value(l) == 1 for l in clause):
                    continue
                for l in clause:
                    if self._lit_value(l) == 0:
                        polarity.setdefault(abs(l), set()).add(1 if l > 0 else -1)
            for var in sorted(polarity):
                signs = polarity[var]
                if len(signs) == 1 and self._value[var] == 0:
                    self._enqueue(var if 1 in signs else -var, implied=True)
                    changed = True
            if changed and not self._propagate():
                return False
        return True

    def _pick_branch_var(self) -> int:
        """Lowest unassigned variable in an unsatisfied clause; 0 if all satisfied."""
        best = 0
        for clause in self.clauses:
            candidate = 0
            satisfied = False
            for x in clause:
                v = self._lit_value(x)
                if v == 1:
                    satisfied = True
                    break
                if v == 0 and (candidate == 0 or abs(x) < candidate):
                    candidate = abs(x)
            if not satisfied and candidate and (best == 0 or candidate < best):
                best = candidate
        return best

    def _undo(self, mark: int) -> None:
        for lit in self._trail[mark:]:
            self._value[abs(lit)] = 0
        del self._trail[mark:]
        self._qhead = mark

    def _search(self) -> bool:
        if self._deadline is not None and time.perf_counter() > self._deadline:
            raise SolverTimeout("DPLL time limit exceeded")
        var = self._pick_branch_var()
        if var == 0:
            return True  # every clause satisfied
        for lit in (var, -var):
            mark = len(self._trail)
            self._stats.decisions += 1
            self._enqueue(lit)
            if self._propagate() and self._search():
                return True
            self._undo(mark)
            self._stats.backtracks += 1
        return False


def solve(num_vars: int, clauses: Iterable[Sequence[int]], assumptions: Iterable[int] = (),
          time_limit: Optional[float] = None) -> SolveResult:
    """Convenience wrapper: build a solver and run one query."""
    return DPLLSolver(num_vars, clauses).solve(assumptions, time_limit)
