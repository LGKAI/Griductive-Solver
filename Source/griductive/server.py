"""Local web server for the GUI (standard library only).

The browser is treated like any other player: it only ever receives the
public state. Hidden statuses and unrevealed clues stay inside the
GameEngine on the server.
"""

from __future__ import annotations

import json
import mimetypes
import random
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from .agent import LogicAgent
from .clues import CRIMINAL, Clue, clue_references, clue_text
from .cnf import CARDINALITY_MODES
from .engine import GameEngine, PuzzleIntegrityError
from .dpll import SolverTimeout
from .entailment import STRATEGIES
from .generator import GenerationFailed, generate
from .puzzle import Character, Puzzle, PuzzleError
from .themes import DEFAULT_THEME, FILE_CAST, THEMES, themed_characters

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
PUZZLE_DIR = ROOT / "puzzles"
MAX_BODY = 2_000_000
MAX_UPLOAD_SIZE = 6
UNIQUENESS_TIME_LIMIT = 20.0  # seconds per SAT call


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class Session:
    engine: GameEngine
    agent: LogicAgent
    log: list[dict] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    sat_calls: int = 0
    round: int = 0  # bumped on restart; moves sent for an older round are refused
    seq: int = 0  # bumped on every change; lets the browser drop out-of-order responses
    theme: str = DEFAULT_THEME
    base_characters: dict[str, Character] = field(default_factory=dict)  # the puzzle's own cast
    base_title: str = ""

    def __post_init__(self) -> None:
        self.base_characters = dict(self.engine.puzzle.characters)
        self.base_title = self.engine.puzzle.title

    def apply_theme(self, theme_id: str) -> None:
        """Re-skin the cast. Cosmetic only: cells, clues, solution and progress are unchanged."""
        puzzle = self.engine.puzzle
        try:
            puzzle.characters = themed_characters(puzzle, self.base_characters, theme_id)
        except ValueError as exc:
            raise ApiError(str(exc)) from None
        puzzle.title = THEMES[theme_id].title_for(puzzle.puzzle_id) or self.base_title
        self.theme = theme_id


class GameStore:
    def __init__(self, max_sessions: int = 64):
        self.sessions: dict[str, Session] = {}
        self.order: list[str] = []
        self.max_sessions = max_sessions
        self.lock = threading.Lock()

    def create(self, puzzle: Puzzle, strategy: str, cardinality: str,
               theme: str = DEFAULT_THEME) -> tuple[str, Session]:
        session = Session(GameEngine(puzzle, strategy, cardinality), LogicAgent(strategy, cardinality))
        try:
            session.apply_theme(theme)
        except ApiError:  # e.g. a 6x6 upload has more characters than the football cast
            session.apply_theme(FILE_CAST)
        game_id = uuid.uuid4().hex[:12]
        with self.lock:
            self.sessions[game_id] = session
            self.order.append(game_id)
            while len(self.order) > self.max_sessions:
                self.sessions.pop(self.order.pop(0), None)
        return game_id, session

    def get(self, game_id: object) -> Session:
        with self.lock:
            session = self.sessions.get(game_id) if isinstance(game_id, str) else None
        if session is None:
            raise ApiError("Unknown or expired game. Please load a puzzle again.", 404)
        return session


STORE = GameStore()


# ------------------------------------------------------------ serialisers
def clue_json(clue: Optional[Clue]) -> Optional[dict]:
    if clue is None:
        return None
    return {"id": clue.clue_id, "type": clue.type, "text": clue_text(clue), "refs": clue_references(clue),
            "data": clue.to_dict()}


def public_state_json(game_id: str, session: Session) -> dict:
    engine = session.engine
    puzzle = engine.puzzle
    state = engine.public_state()
    revealed_clues = {c.clue_id: c for c in state.revealed_clues}
    order = {cell: i for i, cell in enumerate(engine.revealed)}
    cells = []
    for cell in puzzle.board.cells:
        ch = puzzle.characters[cell]
        col, row = puzzle.board.coords(cell)
        known = cell in state.verdicts
        cells.append({
            "cell": cell, "col": col, "row": row, "name": ch.name, "profession": ch.profession,
            "avatar": ch.avatar,
            "known": known,
            "status": (CRIMINAL if state.verdicts[cell] else "innocent") if known else None,
            "initial": cell in puzzle.initial,
            "order": order.get(cell),
            "clue": clue_json(revealed_clues.get(cell)) if known else None,
            "has_clue": puzzle.clues[cell] is not None if known else None,
        })
    analysis = engine.analysis()
    return {
        "game": game_id,
        "puzzle": {"id": puzzle.puzzle_id, "title": puzzle.title, "case_title": session.base_title,
                   "size": puzzle.board.size,
                   "expected": puzzle.meta.get("expected", "SOLVED"), "note": puzzle.meta.get("note")},
        "theme": session.theme,
        "terms": THEMES[session.theme].terms,
        "round": session.round,
        "seq": session.seq,
        "status": engine.status if analysis.consistent else "INCONSISTENT",
        "mistakes": engine.mistakes,
        "lost": {"cell": engine.lost[0], "verdict": engine.lost[1]} if engine.lost else None,
        "solved_count": len(state.verdicts),
        "total": len(puzzle.board.cells),
        "cells": cells,
        "names": {c: puzzle.characters[c].name for c in puzzle.board.cells},
        "revealed_order": list(engine.revealed),
        "kb": analysis.kb_stats,
        "config": {"strategy": engine.strategy, "cardinality": engine.cardinality},
        "sat_calls_total": session.sat_calls + engine.sat_calls,
        "log_offset": max(0, len(session.log) - 200),
        "log": session.log[-200:],
    }


def analysis_json(session: Session) -> dict:
    analysis = session.engine.analysis()
    return {
        "consistent": analysis.consistent,
        "classification": analysis.classification,
        "queries": [q.to_dict() for q in analysis.queries],
        "kb": analysis.kb_stats,
        "solver": analysis.solver.to_dict(),
        "forced": [c for c, _ in analysis.forced],
    }


# ---------------------------------------------------------------- actions
def list_puzzles() -> list[dict]:
    out = []
    for path in sorted(PUZZLE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append({"file": path.stem, "id": data.get("id", path.stem), "title": data.get("title", path.stem),
                        "size": data.get("size"), "expected": data.get("meta", {}).get("expected", "SOLVED"),
                        "waves": data.get("meta", {}).get("waves")})
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError, TypeError):
            continue
    return out


def _theme(body: dict) -> str:
    theme = body.get("theme", DEFAULT_THEME)
    if not isinstance(theme, str) or theme not in THEMES:
        raise ApiError(f"theme must be one of {tuple(THEMES)}")
    return theme


def _config(body: dict) -> tuple[str, str]:
    strategy = body.get("strategy", "filter")
    cardinality = body.get("cardinality", "auto")
    if strategy not in STRATEGIES:
        raise ApiError(f"strategy must be one of {STRATEGIES}")
    if cardinality not in CARDINALITY_MODES:
        raise ApiError(f"cardinality must be one of {CARDINALITY_MODES}")
    return strategy, cardinality


def api_load(body: dict) -> dict:
    strategy, cardinality = _config(body)
    theme = _theme(body)
    try:
        if "file" in body:
            if not isinstance(body["file"], str):
                raise ApiError("'file' must be a string.")
            names = {p.stem: p for p in PUZZLE_DIR.glob("*.json")}
            if body["file"] not in names:
                raise ApiError("Puzzle not found.", 404)
            puzzle = Puzzle.load(names[body["file"]])
        elif "data" in body:
            puzzle = Puzzle.from_dict(body["data"])
            if puzzle.board.size > MAX_UPLOAD_SIZE:
                raise ApiError(f"Uploaded boards are limited to {MAX_UPLOAD_SIZE}x{MAX_UPLOAD_SIZE}.")
        elif "generate" in body:
            gen = body["generate"] or {}
            if not isinstance(gen, dict):
                raise ApiError("'generate' must be an object.")
            size = gen.get("size", 4)
            if type(size) is not int or size not in (3, 4, 5):
                raise ApiError("Generated puzzles must be 3x3, 4x4 or 5x5.")
            seed = gen.get("seed")
            if seed is None:
                seed = random.randrange(1_000_000)
            if not isinstance(seed, int) or isinstance(seed, bool):
                raise ApiError("seed must be an integer")
            puzzle = generate(size, seed=seed, puzzle_id=f"random-{size}x{size}-{seed}")
            puzzle.title += f" (seed {seed})"
        else:
            raise ApiError("Specify 'file', 'data' or 'generate'.")
    except PuzzleError as exc:
        raise ApiError(f"Invalid puzzle: {exc}") from None
    except GenerationFailed as exc:
        raise ApiError(f"{exc}. Please try again.", 503) from None
    game_id, session = STORE.create(puzzle, strategy, cardinality, theme)
    return {"state": public_state_json(game_id, session)}


def _check_round(session: Session, body: dict) -> None:
    """Refuse a move that was sent before a restart (e.g. an auto-solve step in flight)."""
    rnd = body.get("round", session.round)
    if type(rnd) is not int or rnd != session.round:
        raise ApiError("This game was restarted; the move was ignored.", 409)


def api_restart(body: dict) -> dict:
    session = STORE.get(body.get("game"))
    with session.lock:
        session.round += 1
        session.seq += 1
        session.engine.reset()
        session.agent = LogicAgent(session.engine.strategy, session.engine.cardinality)
        session.log.clear()
        session.sat_calls = 0
        return {"state": public_state_json(body["game"], session)}


def api_config(body: dict) -> dict:
    session = STORE.get(body.get("game"))
    strategy, cardinality = _config(body)
    with session.lock:
        engine = session.engine
        engine.strategy, engine.cardinality = strategy, cardinality
        engine.invalidate()
        session.seq += 1
        session.agent.strategy, session.agent.cardinality = strategy, cardinality
        return {"state": public_state_json(body["game"], session)}


def api_verdict(body: dict) -> dict:
    session = STORE.get(body.get("game"))
    with session.lock:
        _check_round(session, body)
        engine = session.engine
        cell, verdict = body.get("cell"), body.get("verdict")
        if not isinstance(cell, str) or not isinstance(verdict, str):
            raise ApiError("'cell' and 'verdict' must be strings.")
        result = engine.submit(cell, verdict)
        session.seq += 1
        entry = {"kind": "player", "cell": result.cell, "verdict": result.verdict, "result": result.status,
                 "message": result.message, "name": engine.puzzle.characters[result.cell].name
                 if engine.board.is_cell(result.cell) else result.cell}
        if result.revealed_clue is not None:
            entry["revealed_text"] = clue_text(result.revealed_clue)
        if result.status != "INVALID":  # malformed moves are not part of the game's history
            session.log.append(entry)
        return {"result": {"status": result.status, "message": result.message, "cell": result.cell,
                           "verdict": result.verdict, "clue": clue_json(result.revealed_clue)},
                "state": public_state_json(body["game"], session)}


def _check_playing(session: Session) -> None:
    if session.engine.status == "LOST":
        raise ApiError("Game over: a contradicted verdict ended this case. Restart to play again.", 409)


def api_hint(body: dict) -> dict:
    session = STORE.get(body.get("game"))
    with session.lock:
        _check_round(session, body)
        _check_playing(session)
        hint = session.agent.hint(session.engine.player_view().public_state())
        return {"hint": hint, "state": public_state_json(body["game"], session)}


def api_step(body: dict) -> dict:
    session = STORE.get(body.get("game"))
    with session.lock:
        _check_round(session, body)
        _check_playing(session)
        entry = session.agent.step(session.engine.player_view()).to_dict()
        session.seq += 1
        session.sat_calls += entry["sat_calls"]
        log_entry = {"kind": "agent", **{k: entry[k] for k in (
            "step", "cell", "name", "verdict", "result", "sat_calls", "active_clues", "revealed_text", "kb", "solver")},
            "queries": entry["sat_queries"],
            "unknown": sum(1 for v in entry["classification"].values() if v == "UNKNOWN"),
            "forced": [c for c, v in entry["classification"].items() if v in ("CRIMINAL", "INNOCENT")]}
        if log_entry["result"] != "SOLVED":  # pressing Step on a solved board adds nothing
            session.log.append(log_entry)
        return {"entry": log_entry, "state": public_state_json(body["game"], session)}


def api_analysis(body: dict) -> dict:
    session = STORE.get(body.get("game"))
    with session.lock:
        return {"analysis": analysis_json(session)}


def api_uniqueness(body: dict) -> dict:
    session = STORE.get(body.get("game"))
    with session.lock:
        try:
            res = session.engine.uniqueness(time_limit=UNIQUENESS_TIME_LIMIT)
        except SolverTimeout:
            raise ApiError("The uniqueness check timed out.", 504) from None
        # Never send the solutions themselves: they are hidden information.
        return {"uniqueness": {"verdict": res.verdict, "solutions_found": res.count, "sat_calls": res.sat_calls,
                               "solver": res.stats.to_dict()}}


ROUTES = {
    "/api/load": api_load,
    "/api/restart": api_restart,
    "/api/config": api_config,
    "/api/verdict": api_verdict,
    "/api/hint": api_hint,
    "/api/step": api_step,
    "/api/analysis": api_analysis,
    "/api/uniqueness": api_uniqueness,
}


# ---------------------------------------------------------------- handler
class Handler(BaseHTTPRequestHandler):
    server_version = "CasebookServer/1.0"
    timeout = 15  # seconds; a client that never sends its body cannot pin a thread

    def log_message(self, fmt: str, *args) -> None:  # keep the console quiet
        pass

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/puzzles":
            self._json(200, {"puzzles": list_puzzles()})
            return
        if path == "/":
            path = "/index.html"
        target = (WEB_DIR / path.lstrip("/")).resolve()
        if WEB_DIR.resolve() not in target.parents or not target.is_file():
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        handler = ROUTES.get(path)
        if handler is None:
            self._json(404, {"error": "Unknown endpoint"})
            return
        try:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError("Invalid Content-Length.") from None
            if length < 0:
                raise ApiError("Invalid Content-Length.")
            if length > MAX_BODY:
                raise ApiError("Request too large.", 413)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ApiError("Request body must be JSON.") from None
            if not isinstance(body, dict):
                raise ApiError("Request body must be a JSON object.")
            self._json(200, handler(body))
        except ApiError as exc:
            self._json(exc.status, {"error": str(exc)})
        except TimeoutError:
            self.close_connection = True
            try:
                self._json(408, {"error": "Request body not received in time."})
            except OSError:
                pass
        except PuzzleIntegrityError:
            # Never echo the details: they would reveal a hidden status.
            self._json(409, {"error": "The puzzle data is corrupt: a provable verdict contradicts its stored solution."})
        except Exception:  # pragma: no cover - defensive
            traceback.print_exc()
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Internal server error (see the server console)."})


def make_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("image/svg+xml", ".svg")
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
