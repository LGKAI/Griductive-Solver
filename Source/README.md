# Casebook: a no-guess Griductive solver (CSC14003 Project 2)

Casebook reimplements the Griductive deduction game. It also provides a logic agent that solves
puzzles **without guessing**, using propositional logic, automatic CNF encoding and a DPLL SAT
solver written from scratch.

## Requirements

- Python **3.10 or newer** (developed and tested on Python 3.14).
- **No third-party packages.** Everything uses the standard library (see `requirements.txt`).
- Any modern browser (Chrome, Edge, Firefox or Safari) for the GUI.

## How to run

```bash
cd Source
python3 main.py                 # starts the GUI and opens http://127.0.0.1:8765
python3 main.py --no-browser --port 9000
```

If port 8765 is busy, the next free port is used. Stop the server with `Ctrl+C`.

Command-line tools:

```bash
python3 main.py --solve puzzles/05-4x4-a.json -v      # agent solves in the terminal, prints the full trace
python3 main.py --solve puzzles/05-4x4-a.json --strategy naive --cardinality counter
python3 main.py --check puzzles/05-4x4-a.json         # uniqueness check of the complete clue set
python3 experiments.py                                # experiments -> results/ (CSV, JSON, Markdown, SVG charts)
python3 experiments.py --quick                        # default configuration only -> results/quick/
python3 -m unittest discover -s tests -v              # test suite
python3 tools/build_puzzles.py                        # regenerate the bundled puzzle set (deterministic seeds)
```

## Using the GUI

| Control | What it does |
|---|---|
| **Case files / Load** | Choose a bundled puzzle and load it (double-clicking also works). |
| **Open file** | Load a puzzle JSON file from disk (format described below). |
| **New (3×3 / 4×4 / 5×5)** | Generate a random puzzle that is guaranteed solvable without guessing. |
| **Characters** | The cast is 30 star football players in national-team colours (incl. Vietnam), with photos from Wikimedia Commons (`web/portraits/CREDITS.md`). Statuses read **Red card** / **Fair play** (logically: criminal / innocent). Purely cosmetic: a board with more than 30 cells keeps the names stored in the puzzle file. |
| Click a face-down card | Accuse the character: **Criminal** (`C`) or **Innocent** (`I`). |
| **Restart** (`R`) | Return to the initial face-up cards (the `R` key asks first if you have made progress). |
| **Hint** (`H`) | Names one character who can be proved now, and highlights the *minimal* set of revealed clues that proves it. The verdict itself is shown only if you ask. |
| **Step** (`N`) / **Auto solve** (`A`) | The logic agent makes one deduction step, or keeps going until the puzzle is solved or stuck. The speed slider sets the delay between steps. |
| Click a revealed clue | Highlights the cells the clue counts (solid ring) and the people it names (dashed ring). `Esc` clears the highlight. |
| **Show solver deductions** | Overlays the current entailment result (forced criminal, forced innocent or unknown) on face-down cards. |
| **Trace** tab | Every move, made by you or by the agent, with its SAT queries (for example `KB ∧ ¬C(B2) → UNSAT`), active clues and newly revealed clue. |
| **Solver** tab | Knowledge-base size (primary/auxiliary variables, clauses), DPLL statistics, query strategy, cardinality encoding, and the uniqueness check. |

The engine reports a rejected verdict as `NOT_PROVABLE` when neither status is forced yet, or as
`CONTRADICTED` when the opposite status is forced. A rejected verdict never reveals anything.
`NOT_PROVABLE` is only a warning (it counts as a mistake). `CONTRADICTED` is **game over**: the
engine stops accepting verdicts, hints and agent steps until the case is restarted
(`GameEngine(sudden_death=False)` restores the old behaviour).

## Adding or replacing a player photo

A player shows the photo `web/portraits/football/<slug>.jpg` (`Văn Hậu` → `van-hau.jpg`), or a
drawn kit avatar if there is none. To crop and install a new photo (macOS, built-in `sips`):

```bash
python3 tools/add_portrait.py football Messi ~/Downloads/messi.jpg --center 0.5 0.25 --size 0.7 --source https://...
```

`--center X Y` is the centre of the square crop as fractions of the image (default `0.5 0.3`),
`--size` its side as a fraction of the shorter side. Restart `main.py` afterwards.

## Architecture

```
Source/
├── main.py                  entry point: GUI server and CLI (--solve, --check)
├── experiments.py           benchmark runner -> results/
├── griductive/
│   ├── board.py             grid geometry, region expressions (row/col/neighbors/list + extensions)
│   ├── clues.py             clue templates: validation, direct semantic evaluator, text rendering
│   ├── cnf.py               variable map, CNF builder, Tseitin gates, cardinality encodings, clue encoder
│   ├── dpll.py              DPLL SAT solver (unit propagation, backtracking, statistics)
│   ├── knowledge.py         PublicState (what the agent may see) and KB_t construction
│   ├── entailment.py        CRIMINAL / INNOCENT / UNKNOWN / INCONSISTENT classification, hints, uniqueness
│   ├── engine.py            Game Engine: owns the hidden solution, judges verdicts, reveals clues
│   ├── agent.py             Logic Agent: deduction loop and trace
│   ├── generator.py         random no-guess puzzle generator
│   ├── puzzle.py            puzzle file format and validation
│   ├── themes.py            football cast (names, photos, kits) and status words
│   └── server.py            local JSON API for the web GUI (standard library http.server)
├── web/                     index.html, style.css, app.js (no build step, no frameworks)
├── puzzles/                 bundled puzzles (3×3, 4×4, 5×5 and two failure cases)
├── results/                 experiment output
├── tests/test_solver.py     unit and cross-check tests (encoder vs evaluator, DPLL vs brute force, agent)
├── tests/test_server.py     HTTP API tests (validation, no hidden-information leaks)
└── tools/build_puzzles.py   regenerates puzzles/
```

**Engine and agent are separated.** `GameEngine` holds the full puzzle. `LogicAgent` is given only
a `PlayerView` (`engine.player_view()`), which has exactly two methods: `public_state()` returns a
`PublicState` with the revealed clues and proved verdicts, and `submit(cell, verdict)` submits a verdict. The browser is treated the same way: the server never sends hidden
statuses or unrevealed clues.

## Clue language

Core templates: `FACT`, `SAME`, `DIFFERENT`, `EXACTLY`, `AT_LEAST`, `AT_MOST`. Counting clues accept
`"who": "innocent"` to count innocents instead of criminals.

Extensions:

| Extension | Example |
|---|---|
| `PARITY` | `{"type":"PARITY","parity":"odd","region":{"kind":"col","index":"A"}}` |
| `COMPARE` | `{"type":"COMPARE","op":"more","left":{"kind":"row","index":1},"right":{"kind":"row","index":2}}` |
| `CONNECTED` | `{"type":"CONNECTED","region":{"kind":"row","index":3},"who":"innocent"}` |
| `IMPLIES` | `{"type":"IMPLIES","if":{"cell":"A1","status":"criminal"},"then":{"cell":"B2","status":"innocent"}}` |
| Advanced regions | `all`, `corners`, `edge`, `ray` (left/right/above/below of a cell), `between`, `common_neighbors`, `intersect`, `union`, `minus` |

## Puzzle file format

```json
{
  "id": "my-case", "title": "My Case", "size": 3, "initial": ["B2"],
  "characters": [
    {"cell": "A1", "name": "Abel", "profession": "Cook", "status": "criminal",
     "clue": {"type": "EXACTLY", "k": 1, "region": {"kind": "neighbors", "of": "B2"}}}
  ]
}
```

`characters` must cover every cell. `status` is the hidden solution. `initial` lists the face-up
cards. Names must be unique and in alphabetical order, row by row (A1, B1, …, A2, …), as in the
original game. A puzzle is rejected if any clue is false under its own solution.
