"""API 集成测试。未安装 fastapi 时整体跳过（如仅跑核心算法的环境）。"""

import unittest

try:
    from fastapi.testclient import TestClient

    from app.main import app
except ImportError as exc:  # pragma: no cover
    raise unittest.SkipTest(f"fastapi 未安装，跳过 API 集成测试: {exc}")

client = TestClient(app)

VALID_PAYLOAD = {
    "source_voltage": 48.0,
    "min_voltage": 40.0,
    "segments": [
        {"id": "s1", "parent": "source", "child": "a",
         "resistance": 0.1, "rated_current": 30.0},
        {"id": "s2", "parent": "a", "child": "b",
         "resistance": 0.05, "rated_current": 10.0},
    ],
    "loads": [
        {"node": "a", "current": 5.0},
        {"node": "b", "current": 10.0},
    ],
}


class ApiTest(unittest.TestCase):
    def test_health(self):
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_evaluate_ok(self):
        resp = client.post("/evaluate", json=VALID_PAYLOAD)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        currents = {s["id"]: s["current"] for s in body["segments"]}
        self.assertEqual(currents, {"s1": 15.0, "s2": 10.0})
        voltages = {n["node"]: n["voltage"] for n in body["nodes"]}
        self.assertEqual(voltages, {"source": 48.0, "a": 46.5, "b": 46.0})

    def test_evaluate_violations(self):
        payload = {
            "source_voltage": 24.0,
            "min_voltage": 22.0,
            "segments": [
                {"id": "s1", "parent": "source", "child": "a",
                 "resistance": 0.5, "rated_current": 5.0},
            ],
            "loads": [{"node": "a", "current": 12.0}],
        }
        resp = client.post("/evaluate", json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["ok"])
        self.assertEqual(
            [s["id"] for s in body["violations"]["over_rated_segments"]], ["s1"]
        )
        self.assertEqual(
            [n["node"] for n in body["violations"]["under_voltage_nodes"]], ["a"]
        )

    def test_invalid_tree_returns_400(self):
        payload = dict(VALID_PAYLOAD)
        payload["segments"] = [
            {"id": "s1", "parent": "source", "child": "a",
             "resistance": 0.1, "rated_current": 10.0},
            {"id": "s2", "parent": "x", "child": "b",
             "resistance": 0.1, "rated_current": 10.0},
        ]
        resp = client.post("/evaluate", json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not defined", resp.json()["detail"])

    def test_non_positive_source_voltage_returns_422(self):
        for value in (0.0, -48.0):
            payload = dict(VALID_PAYLOAD)
            payload["source_voltage"] = value
            resp = client.post("/evaluate", json=payload)
            self.assertEqual(resp.status_code, 422)

    def test_negative_resistance_returns_422(self):
        payload = dict(VALID_PAYLOAD)
        payload["segments"] = [
            {"id": "s1", "parent": "source", "child": "a",
             "resistance": -0.1, "rated_current": 10.0},
        ]
        resp = client.post("/evaluate", json=payload)
        self.assertEqual(resp.status_code, 422)

    def test_negative_load_returns_422(self):
        payload = dict(VALID_PAYLOAD)
        payload["loads"] = [{"node": "a", "current": -1.0}]
        resp = client.post("/evaluate", json=payload)
        self.assertEqual(resp.status_code, 422)

    def test_unknown_field_returns_422(self):
        payload = dict(VALID_PAYLOAD)
        payload["bogus"] = 1
        resp = client.post("/evaluate", json=payload)
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
