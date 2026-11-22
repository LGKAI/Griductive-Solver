"""Bộ kiểm thử API HTTP của máy chủ web Casebook. Chạy bằng: python -m unittest discover -s tests -v"""

from __future__ import annotations

import json
import socket
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from griductive.server import make_server  # noqa: E402
from griductive.puzzle import name_key  # noqa: E402


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def post(self, path, body):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read() or b"{}")

    def load(self, file="05-4x4-a"):
        status, data = self.post("/api/load", {"file": file})
        self.assertEqual(status, 200, data)
        return data["state"]

    def test_malformed_requests_are_client_errors(self):
        game = self.load()["game"]
        bad = [
            ("/api/load", {"file": ["x"]}), ("/api/load", {"generate": 5}), ("/api/load", {"generate": [1]}),
            ("/api/load", {"generate": {"size": 3.0}}), ("/api/load", {"generate": {"size": True}}),
            ("/api/load", {"data": {"size": 3}}), ("/api/load", {"file": "../../etc/passwd"}),
            ("/api/verdict", {"game": game, "cell": ["A1"], "verdict": "CRIMINAL"}),
            ("/api/verdict", {"game": game, "cell": {}, "verdict": "CRIMINAL"}),
            ("/api/verdict", {"game": game, "cell": "A1", "verdict": 3}),
            ("/api/config", {"game": game, "strategy": "x"}),
            ("/api/step", {"game": ["nope"]}), ("/api/hint", {}), ("/api/load", b"[1, 2]"), ("/api/load", b"{bad"),
        ]
        for path, body in bad:
            status, data = self.post(path, body)
            self.assertTrue(400 <= status < 500, f"{path} {body!r} -> {status} {data}")
            self.assertIn("error", data)

    def test_bad_content_length(self):
        for header in (b"abc", b"-1"):
            with socket.create_connection(("127.0.0.1", self.port), timeout=5) as sock:
                sock.sendall(b"POST /api/load HTTP/1.1\r\nHost: x\r\nContent-Length: " + header + b"\r\n\r\n")
                reply = sock.recv(200)
            self.assertIn(b" 400 ", reply.split(b"\r\n")[0])

    def test_no_hidden_information_in_state(self):
        state = self.load()
        for cell in state["cells"]:
            if not cell["known"]:
                self.assertIsNone(cell["status"])
                self.assertIsNone(cell["clue"])
                self.assertIsNone(cell["has_clue"])
        status, data = self.post("/api/uniqueness", {"game": state["game"]})
        self.assertEqual(status, 200)
        self.assertNotIn("solutions", data["uniqueness"])
        self.assertEqual(data["uniqueness"]["verdict"], "UNIQUE")

    def test_rejections_do_not_inflate_sat_calls(self):
        state = self.load()
        game = state["game"]
        _, data = self.post("/api/analysis", {"game": game})
        unknown = [c for c, v in data["analysis"]["classification"].items() if v == "UNKNOWN"][0]
        totals = []
        for _ in range(3):
            _, res = self.post("/api/verdict", {"game": game, "cell": unknown, "verdict": "CRIMINAL"})
            self.assertEqual(res["result"]["status"], "NOT_PROVABLE")
            totals.append(res["state"]["sat_calls_total"])
        self.assertEqual(len(set(totals)), 1, totals)
        self.assertEqual(res["state"]["mistakes"], 3)

    def test_agent_step_and_restart(self):
        game = self.load("01-3x3-a")["game"]
        for _ in range(20):
            _, data = self.post("/api/step", {"game": game})
            if data["entry"]["result"] != "ACCEPTED":
                break
        self.assertEqual(data["state"]["status"], "SOLVED")
        _, data = self.post("/api/restart", {"game": game})
        self.assertEqual(data["state"]["solved_count"], 1)
        self.assertEqual(data["state"]["log"], [])

    def test_integrity_error_is_not_leaked(self):
        # A corrupt upload: the clue says A1 is criminal but the stored solution says innocent.
        chars = [{"cell": c, "name": n, "profession": "x", "status": "innocent", "clue": None}
                 for c, n in zip(["A1", "B1", "A2", "B2"], ["Ann", "Bob", "Cy", "Di"])]
        chars[3]["clue"] = {"type": "FACT", "cell": "A1", "status": "criminal"}
        data = {"id": "bad", "size": 2, "initial": ["B2"], "meta": {"allow_false_clues": True}, "characters": chars}
        status, res = self.post("/api/load", {"data": data})
        self.assertEqual(status, 200)
        game = res["state"]["game"]
        # The agent stops with ERROR; the card is not revealed and nothing hidden is echoed.
        status, res = self.post("/api/step", {"game": game})
        self.assertEqual(status, 200)
        self.assertEqual(res["entry"]["result"], "ERROR")
        self.assertFalse(next(c for c in res["state"]["cells"] if c["cell"] == "A1")["known"])
        # A player submitting the same (provable) verdict gets a generic 409.
        status, res = self.post("/api/verdict", {"game": game, "cell": "A1", "verdict": "CRIMINAL"})
        self.assertEqual(status, 409)
        self.assertNotIn("A1", res["error"])
        self.assertNotIn("innocent", res["error"].lower())

    def test_fresh_game_has_no_sat_calls(self):
        state = self.load()
        self.assertEqual(state["sat_calls_total"], 0)
        status, data = self.post("/api/analysis", {"game": state["game"]})
        self.assertEqual(status, 200)
        _, data = self.post("/api/restart", {"game": state["game"]})
        self.assertEqual(data["state"]["sat_calls_total"], 0)

    def test_bad_cells_and_regions_are_client_errors(self):
        game = self.load("01-3x3-a")["game"]
        status, _ = self.post("/api/verdict", {"game": game, "cell": "A2\n", "verdict": "CRIMINAL"})
        self.assertEqual(status, 200)  # INVALID result, not a crash
        base = json.loads((ROOT / "puzzles" / "01-3x3-a.json").read_text(encoding="utf-8"))
        for mutate in (lambda d: d.update(initial=["B2\n"]),
                       lambda d: d["characters"][0].update(clue={"type": "EXACTLY", "k": 1, "region": {
                           "kind": "ray", "of": "B2", "dir": ["left"]}})):
            data = json.loads(json.dumps(base))
            mutate(data)
            status, res = self.post("/api/load", {"data": data})
            self.assertEqual(status, 400, res)

    def test_moves_from_before_a_restart_are_refused(self):
        state = self.load("01-3x3-a")
        game, old_round = state["game"], state["round"]
        _, data = self.post("/api/restart", {"game": game})
        self.assertEqual(data["state"]["round"], old_round + 1)
        status, _ = self.post("/api/step", {"game": game, "round": old_round})
        self.assertEqual(status, 409)
        _, data = self.post("/api/analysis", {"game": game})
        status, data = self.post("/api/step", {"game": game, "round": old_round + 1})
        self.assertEqual(status, 200)

    def test_football_cast_is_default_and_hides_nothing(self):
        state = self.load("05-4x4-a")
        self.assertEqual(state["theme"], "football")
        self.assertEqual(state["terms"]["criminal"]["label"], "Red card")
        names = [c["name"] for c in state["cells"]]
        self.assertEqual(names, sorted(names, key=name_key))
        self.assertTrue(all(c["avatar"]["kind"] == "football" for c in state["cells"]))
        for cell in state["cells"]:
            if not cell["known"]:
                self.assertIsNone(cell["status"])
                self.assertIsNone(cell["clue"])
        game = state["game"]
        _, data = self.post("/api/step", {"game": game})
        self.assertGreater(data["state"]["seq"], state["seq"])
        status, _ = self.post("/api/step", {"game": game, "round": True})
        self.assertEqual(status, 409)
        status, _ = self.post("/api/theme", {"game": game, "theme": "football"})
        self.assertEqual(status, 404)  # the cast cannot be switched any more
        status, _ = self.post("/api/load", {"file": "05-4x4-a", "theme": "nope"})
        self.assertEqual(status, 400)
        status, data = self.post("/api/load", {"file": "09-5x5-a"})
        self.assertEqual(data["state"]["theme"], "football")  # 25 cells <= 30 players

    def test_board_larger_than_the_cast_keeps_file_names(self):
        chars = [{"cell": f"{col}{row}", "name": f"P{row:02d}{col}", "profession": "", "status": "innocent", "clue": None}
                 for row in range(1, 7) for col in "ABCDEF"]
        data = {"id": "six", "size": 6, "initial": ["A1"], "characters": chars}
        status, res = self.post("/api/load", {"data": data})
        self.assertEqual(status, 200, res)
        self.assertEqual(res["state"]["theme"], "classic")
        self.assertEqual(res["state"]["cells"][0]["name"], "P01A")

if __name__ == "__main__":
    unittest.main()
