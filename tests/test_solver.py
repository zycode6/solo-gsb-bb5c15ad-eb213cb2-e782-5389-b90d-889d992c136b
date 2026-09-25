"""核心算法单元测试（仅依赖标准库，可直接用 unittest 运行）。"""

import unittest

from app.solver import TreeError, evaluate


def seg(sid, parent, child, resistance, rated):
    return {
        "id": sid,
        "parent": parent,
        "child": child,
        "resistance": resistance,
        "rated_current": rated,
    }


class EvaluateTest(unittest.TestCase):
    def test_happy_path(self):
        # source -s1-> a -s2-> b；a 负载 5A，b 负载 10A
        result = evaluate(
            source_voltage=48.0,
            min_voltage=40.0,
            segments=[
                seg("s1", "source", "a", 0.1, 30.0),
                seg("s2", "a", "b", 0.05, 10.0),
            ],
            loads=[
                {"node": "a", "current": 5.0},
                {"node": "b", "current": 10.0},
            ],
        )
        self.assertTrue(result["ok"])
        currents = {s["id"]: s["current"] for s in result["segments"]}
        self.assertEqual(currents, {"s1": 15.0, "s2": 10.0})
        voltages = {n["node"]: n["voltage"] for n in result["nodes"]}
        self.assertEqual(voltages, {"source": 48.0, "a": 46.5, "b": 46.0})
        self.assertEqual(result["violations"]["over_rated_segments"], [])
        self.assertEqual(result["violations"]["under_voltage_nodes"], [])

    def test_over_rated_and_under_voltage(self):
        result = evaluate(
            source_voltage=24.0,
            min_voltage=22.0,
            segments=[
                seg("s1", "source", "a", 0.5, 5.0),   # 承载 12A > 5A
                seg("s2", "a", "b", 0.5, 20.0),
            ],
            loads=[
                {"node": "a", "current": 2.0},
                {"node": "b", "current": 10.0},
            ],
        )
        self.assertFalse(result["ok"])
        over = [s["id"] for s in result["violations"]["over_rated_segments"]]
        self.assertEqual(over, ["s1"])
        # V_a = 24 - 12*0.5 = 18，V_b = 18 - 10*0.5 = 13，均低于 22V
        under = [n["node"] for n in result["violations"]["under_voltage_nodes"]]
        self.assertEqual(under, ["a", "b"])

    def test_node_min_voltage_override(self):
        result = evaluate(
            source_voltage=48.0,
            min_voltage=40.0,
            segments=[seg("s1", "source", "a", 0.5, 100.0)],
            loads=[{"node": "a", "current": 10.0, "min_voltage": 45.0}],
        )
        # V_a = 43V，全局阈值 40V 不欠压，但节点级阈值 45V 触发欠压
        self.assertFalse(result["ok"])
        under = result["violations"]["under_voltage_nodes"]
        self.assertEqual([n["node"] for n in under], ["a"])
        self.assertEqual(under[0]["min_voltage"], 45.0)

    def test_source_only_tree(self):
        result = evaluate(
            source_voltage=12.0,
            min_voltage=10.0,
            segments=[],
            loads=[{"node": "source", "current": 3.0}],
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["nodes"][0]["voltage"], 12.0)

    def test_disconnected_tree(self):
        with self.assertRaisesRegex(TreeError, "not defined"):
            evaluate(
                source_voltage=48.0,
                min_voltage=40.0,
                segments=[
                    seg("s1", "source", "a", 0.1, 10.0),
                    seg("s2", "x", "b", 0.1, 10.0),  # x 不在树中
                ],
                loads=[],
            )

    def test_cycle_not_reachable_from_source(self):
        with self.assertRaisesRegex(TreeError, "not connected"):
            evaluate(
                source_voltage=48.0,
                min_voltage=40.0,
                segments=[
                    seg("s1", "source", "a", 0.1, 10.0),
                    seg("s2", "b", "c", 0.1, 10.0),
                    seg("s3", "c", "b", 0.1, 10.0),  # b<->c 成环
                ],
                loads=[],
            )

    def test_multiple_parents(self):
        with self.assertRaisesRegex(TreeError, "more than one parent"):
            evaluate(
                source_voltage=48.0,
                min_voltage=40.0,
                segments=[
                    seg("s1", "source", "a", 0.1, 10.0),
                    seg("s2", "source", "b", 0.1, 10.0),
                    seg("s3", "b", "a", 0.1, 10.0),
                ],
                loads=[],
            )

    def test_source_as_child(self):
        with self.assertRaisesRegex(TreeError, "must not appear as a child"):
            evaluate(
                source_voltage=48.0,
                min_voltage=40.0,
                segments=[seg("s1", "a", "source", 0.1, 10.0)],
                loads=[],
            )

    def test_self_loop(self):
        with self.assertRaisesRegex(TreeError, "to itself"):
            evaluate(
                source_voltage=48.0,
                min_voltage=40.0,
                segments=[seg("s1", "a", "a", 0.1, 10.0)],
                loads=[],
            )

    def test_duplicate_segment_id(self):
        with self.assertRaisesRegex(TreeError, "duplicate segment id"):
            evaluate(
                source_voltage=48.0,
                min_voltage=40.0,
                segments=[
                    seg("s1", "source", "a", 0.1, 10.0),
                    seg("s1", "source", "b", 0.1, 10.0),
                ],
                loads=[],
            )

    def test_unknown_load_node(self):
        with self.assertRaisesRegex(TreeError, "unknown node"):
            evaluate(
                source_voltage=48.0,
                min_voltage=40.0,
                segments=[seg("s1", "source", "a", 0.1, 10.0)],
                loads=[{"node": "ghost", "current": 1.0}],
            )

    def test_duplicate_load(self):
        with self.assertRaisesRegex(TreeError, "duplicate load"):
            evaluate(
                source_voltage=48.0,
                min_voltage=40.0,
                segments=[seg("s1", "source", "a", 0.1, 10.0)],
                loads=[
                    {"node": "a", "current": 1.0},
                    {"node": "a", "current": 2.0},
                ],
            )


if __name__ == "__main__":
    unittest.main()
