"""Automatic CNF encoding of clues.

Variables are DIMACS-style positive integers; a literal is ``+v`` or ``-v``.
Primary variable ``C_i`` (true = criminal) is numbered by the row-major index
of cell ``i`` plus one, so the mapping is deterministic. Auxiliary variables
introduced by an encoding are numbered after all primary variables.

Cardinality constraints use one of two encodings:

* ``direct``  - combinatorial (binomial) encoding, no auxiliary variables::

      AT_MOST k  over x_1..x_n:  for every (k+1)-subset S:   OR_{i in S} -x_i
      AT_LEAST k over x_1..x_n:  for every (n-k+1)-subset S: OR_{i in S}  x_i

* ``counter`` - a unary counter (sequential sum) with Tseitin gates:
  ``s[i][j] <-> (at least j of x_1..x_i are true)`` defined by
  ``s[i][j] = s[i-1][j] OR (x_i AND s[i-1][j-1])``.

``auto`` uses ``direct`` unless it would generate too many clauses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import comb
from typing import Iterable, Sequence, Union

from .board import Board
from .clues import CRIMINAL, Clue

Lit = int
# A literal-or-constant: an int literal, or the Python constants True / False.
Term = Union[int, bool]

CARDINALITY_MODES = ("auto", "direct", "counter")
DIRECT_CLAUSE_LIMIT = 300  # 'auto' switches to the counter above this
DIRECT_HARD_LIMIT = 200_000  # even 'direct' falls back to the counter above this (memory guard)


class VarMap:
    """Deterministic mapping between cells and primary variables."""

    def __init__(self, board: Board):
        self.board = board
        self._var = {cell: i + 1 for i, cell in enumerate(board.cells)}
        self._cell = {v: c for c, v in self._var.items()}

    @property
    def num_primary(self) -> int:
        return len(self._var)

    def var(self, cell: str) -> int:
        return self._var[cell]

    def cell(self, var: int) -> str:
        return self._cell[var]

    def is_primary(self, var: int) -> bool:
        return var in self._cell

    def literal(self, cell: str, who: str = CRIMINAL) -> int:
        """Literal that is true when ``cell`` has status ``who``."""
        v = self._var[cell]
        return v if who == CRIMINAL else -v

    def items(self):
        return self._var.items()


@dataclass
class CNF:
    """A clause database with an auxiliary-variable allocator."""

    num_primary: int
    clauses: list[list[int]] = field(default_factory=list)
    num_vars: int = 0
    origins: list[str] = field(default_factory=list)  # clause index -> source tag

    def __post_init__(self) -> None:
        self.num_vars = max(self.num_vars, self.num_primary)
        self._tag = ""

    @property
    def num_aux(self) -> int:
        return self.num_vars - self.num_primary

    def new_var(self) -> int:
        self.num_vars += 1
        return self.num_vars

    def set_tag(self, tag: str) -> None:
        self._tag = tag

    def add(self, clause: Iterable[Term]) -> None:
        """Add a clause given as literals and/or constants (simplified on the fly)."""
        lits: list[int] = []
        for t in clause:
            if t is True:
                return  # clause already satisfied
            if t is False:
                continue
            lits.append(t)
        # drop duplicates, detect tautologies
        seen: set[int] = set()
        out: list[int] = []
        for lit in lits:
            if -lit in seen:
                return
            if lit not in seen:
                seen.add(lit)
                out.append(lit)
        self.clauses.append(out)
        self.origins.append(self._tag)

    # ----------------------------------------------------- Tseitin gates
    def gate_and(self, a: Term, b: Term) -> Term:
        if a is False or b is False:
            return False
        if a is True:
            return b
        if b is True:
            return a
        if a == b:
            return a
        if a == -b:
            return False
        z = self.new_var()
        self.add([-z, a])
        self.add([-z, b])
        self.add([z, -a, -b])
        return z

    def gate_or(self, a: Term, b: Term) -> Term:
        if a is True or b is True:
            return True
        if a is False:
            return b
        if b is False:
            return a
        if a == b:
            return a
        if a == -b:
            return True
        z = self.new_var()
        self.add([z, -a])
        self.add([z, -b])
        self.add([-z, a, b])
        return z

    def gate_xor(self, a: Term, b: Term) -> Term:
        if isinstance(a, bool) and isinstance(b, bool):
            return a != b
        if a is False:
            return b
        if b is False:
            return a
        if a is True:
            return -b  # type: ignore[operator]
        if b is True:
            return -a  # type: ignore[operator]
        if a == b:
            return False
        if a == -b:
            return True
        z = self.new_var()
        self.add([-z, a, b])
        self.add([-z, -a, -b])
        self.add([z, -a, b])
        self.add([z, a, -b])
        return z

    def assert_term(self, t: Term, value: bool = True) -> None:
        """Force a literal-or-constant to ``value`` (False constant -> empty clause)."""
        if isinstance(t, bool):
            if t != value:
                self.add([])
            return
        self.add([t if value else -t])


# ------------------------------------------------- cardinality encodings
def unary_counter(cnf: CNF, lits: Sequence[int], upto: int) -> list[Term]:
    """Return ``r`` with ``r[j] <-> (sum(lits) >= j)`` for ``j = 0..upto``.

    ``r[0]`` is the constant True; entries beyond ``len(lits)`` are False.
    """
    upto = max(0, upto)
    prev: list[Term] = [True] + [False] * upto
    for x in lits:
        cur: list[Term] = [True]
        for j in range(1, upto + 1):
            cur.append(cnf.gate_or(prev[j], cnf.gate_and(x, prev[j - 1])))
        prev = cur
    return prev


def encode_at_most(cnf: CNF, lits: Sequence[int], k: int, mode: str = "auto") -> None:
    n = len(lits)
    if k >= n:
        return
    if k < 0:
        cnf.add([])
        return
    if _use_direct(mode, n, k + 1):
        for subset in combinations(lits, k + 1):
            cnf.add([-x for x in subset])
    else:
        r = unary_counter(cnf, lits, k + 1)
        cnf.assert_term(r[k + 1], False)


def encode_at_least(cnf: CNF, lits: Sequence[int], k: int, mode: str = "auto") -> None:
    n = len(lits)
    if k <= 0:
        return
    if k > n:
        cnf.add([])
        return
    if _use_direct(mode, n, n - k + 1):
        for subset in combinations(lits, n - k + 1):
            cnf.add(list(subset))
    else:
        r = unary_counter(cnf, lits, k)
        cnf.assert_term(r[k], True)


def _use_direct(mode: str, n: int, subset_size: int) -> bool:
    if mode == "direct":
        return comb(n, subset_size) <= DIRECT_HARD_LIMIT
    if mode == "counter":
        return False
    return comb(n, subset_size) <= DIRECT_CLAUSE_LIMIT


# -------------------------------------------------------------- encoder
class ClueEncoder:
    """Converts validated :class:`Clue` objects into clauses of a :class:`CNF`."""

    def __init__(self, varmap: VarMap, cardinality: str = "auto"):
        if cardinality not in CARDINALITY_MODES:
            raise ValueError(f"cardinality must be one of {CARDINALITY_MODES}")
        self.varmap = varmap
        self.mode = cardinality

    def _lits(self, cells: Iterable[str], who: str) -> list[int]:
        return [self.varmap.literal(c, who) for c in cells]

    def encode(self, cnf: CNF, clue: Clue) -> None:
        p, t = clue.params, clue.type
        vm = self.varmap
        if t == "FACT":
            cnf.add([vm.literal(p["cell"], p["status"])])
        elif t == "SAME":  # a <-> b  ==  (-a v b) & (a v -b)
            a, b = vm.var(p["a"]), vm.var(p["b"])
            cnf.add([-a, b])
            cnf.add([a, -b])
        elif t == "DIFFERENT":  # a xor b  ==  (a v b) & (-a v -b)
            a, b = vm.var(p["a"]), vm.var(p["b"])
            cnf.add([a, b])
            cnf.add([-a, -b])
        elif t == "EXACTLY":
            lits = self._lits(p["region"], p["who"])
            encode_at_least(cnf, lits, p["k"], self.mode)
            encode_at_most(cnf, lits, p["k"], self.mode)
        elif t == "AT_LEAST":
            encode_at_least(cnf, self._lits(p["region"], p["who"]), p["k"], self.mode)
        elif t == "AT_MOST":
            encode_at_most(cnf, self._lits(p["region"], p["who"]), p["k"], self.mode)
        elif t == "PARITY":
            self._parity(cnf, self._lits(p["region"], p["who"]), p["parity"] == "odd")
        elif t == "COMPARE":
            self._compare(cnf, self._lits(p["left"], p["who"]), self._lits(p["right"], p["who"]), p["op"])
        elif t == "CONNECTED":
            # Ordered segment l_1..l_m: no gap between two selected cells,
            # i.e. for all i < j < k:  l_i & l_k -> l_j.
            lits = self._lits(p["region"], p["who"])
            for i in range(len(lits)):
                for k in range(i + 2, len(lits)):
                    for j in range(i + 1, k):
                        cnf.add([-lits[i], -lits[k], lits[j]])
        elif t == "IMPLIES":  # premise -> conclusion  ==  -premise v conclusion
            (ca, sa), (cb, sb) = p["if"], p["then"]
            cnf.add([-vm.literal(ca, sa), vm.literal(cb, sb)])
        else:
            raise ValueError(f"no encoder for clue type {t}")

    @staticmethod
    def _parity(cnf: CNF, lits: Sequence[int], odd: bool) -> None:
        """XOR chain p_i = p_{i-1} xor x_i (Tseitin), then force p_n = odd."""
        acc: Term = False
        for x in lits:
            acc = cnf.gate_xor(acc, x)
        cnf.assert_term(acc, odd)

    @staticmethod
    def _compare(cnf: CNF, left: Sequence[int], right: Sequence[int], op: str) -> None:
        """Compare two counts using unary counters L[j] <-> |left| >= j, R[j] likewise."""
        if op == "fewer":
            left, right, op = right, left, "more"
        size = max(len(left), len(right)) + 1
        lc = unary_counter(cnf, left, size)
        rc = unary_counter(cnf, right, size)
        if op == "equal":
            for j in range(1, size + 1):
                # L[j] <-> R[j]
                cnf.add([_neg(lc[j]), rc[j]])
                cnf.add([lc[j], _neg(rc[j])])
        else:  # more: |left| > |right|  <=>  for all j >= 0: R[j] -> L[j+1]
            for j in range(0, size):
                cnf.add([_neg(rc[j]), lc[j + 1]])


def _neg(t: Term) -> Term:
    if isinstance(t, bool):
        return not t
    return -t
