"""Unit tests for code/controller/sdn_logic.py (no Ryu/Mininet needed).

    python3 -m unittest discover -s support/tests -v
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'code' / 'controller'))

from sdn_logic import (BASE_COSTS, AnomalyDetector, Config, base_cost, dijkstra,  # noqa: E402
                       dynamic_cost, link_key, path_cost)


def graph(extra=None):
    """Static mesh graph, optionally with extra cost added per link."""
    extra = extra or {}
    g = {n: {} for n in range(1, 7)}
    for (a, b), c in BASE_COSTS.items():
        w = c + extra.get((a, b), 0)
        g[a][b] = g[b][a] = w
    return g


class TestTopologyCosts(unittest.TestCase):
    def test_eleven_symmetric_links(self):
        self.assertEqual(len(BASE_COSTS), 11)
        self.assertEqual(base_cost(6, 2), base_cost(2, 6))
        self.assertEqual(base_cost(2, 6), 14)

    def test_default_cost(self):
        self.assertEqual(base_cost(1, 6), 10)


class TestDijkstra(unittest.TestCase):
    def test_h1_h6_primary(self):
        self.assertEqual(dijkstra(graph(), 1, 6), ([1, 2, 6], 19))

    def test_attacker_paths(self):
        self.assertEqual(dijkstra(graph(), 2, 3)[0], [2, 3])
        self.assertEqual(dijkstra(graph(), 2, 6)[0], [2, 6])
        # h5->h6 does NOT use s5-s6 with the given costs.
        self.assertEqual(dijkstra(graph(), 5, 6), ([5, 3, 6], 16))

    def test_case_b_reroutes(self):
        self.assertEqual(dijkstra(graph({(2, 6): 30}), 1, 6), ([1, 2, 3, 6], 22))

    def test_case_a_and_c_do_not_reroute(self):
        self.assertEqual(dijkstra(graph({(2, 3): 30}), 1, 6)[0], [1, 2, 6])
        self.assertEqual(dijkstra(graph({(5, 6): 30, (3, 5): 30}), 1, 6)[0], [1, 2, 6])

    def test_missing_node(self):
        self.assertEqual(dijkstra(graph(), 1, 99), (None, float('inf')))

    def test_path_cost(self):
        self.assertEqual(path_cost(graph(), [1, 2, 3, 6]), 22)
        self.assertEqual(path_cost(graph(), [1, 6]), float('inf'))


class TestCostModel(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        self.cfg.alpha, self.cfg.beta, self.cfg.link_capacity_bps = 10.0, 30.0, 40e6

    def test_equation_1(self):
        self.assertAlmostEqual(dynamic_cost(14, 0, False, self.cfg), 14)
        self.assertAlmostEqual(dynamic_cost(14, 20e6, False, self.cfg), 19)
        self.assertAlmostEqual(dynamic_cost(14, 20e6, True, self.cfg), 49)

    def test_utilisation_clamped(self):
        self.assertAlmostEqual(dynamic_cost(14, 80e6, False, self.cfg), 24)

    def test_beta_large_enough_to_reroute_case_b(self):
        # backup path is 3 more expensive; beta + margin must exceed that
        self.assertGreater(self.cfg.beta, 22 - 19 + self.cfg.reroute_margin)

    def test_link_key(self):
        self.assertEqual(link_key(6, 2), (2, 6))


class TestDetector(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        self.cfg.warmup_samples, self.cfg.min_attack_pps, self.cfg.consecutive = 5, 500, 1
        self.det = AnomalyDetector(self.cfg)

    def feed(self, ip, rates):
        return [self.det.update(ip, r) for r in rates]

    def test_ping_then_flood_is_flagged(self):
        self.assertFalse(any(self.feed('10.0.0.2', [1, 1, 1, 1, 1, 1])))
        self.assertTrue(self.det.update('10.0.0.2', 4000))

    def test_steady_iperf_not_flagged(self):
        self.assertFalse(any(self.feed('10.0.0.1', [850 + (i % 3) * 10 for i in range(30)])))

    def test_no_detection_during_warmup(self):
        self.assertFalse(any(self.feed('10.0.0.5', [1, 4000, 4000])))

    def test_anomalous_samples_not_learned(self):
        self.feed('10.0.0.2', [1] * 6)
        before = self.det.baseline('10.0.0.2')
        self.det.update('10.0.0.2', 4000)
        self.assertEqual(self.det.baseline('10.0.0.2'), before)

    def test_floor_blocks_small_bursts(self):
        self.feed('10.0.0.3', [1] * 6)
        self.assertFalse(self.det.update('10.0.0.3', 50))   # 50x baseline but below 500 pps

    def test_consecutive(self):
        self.cfg.consecutive = 2
        self.feed('10.0.0.2', [1] * 6)
        self.assertFalse(self.det.update('10.0.0.2', 4000))
        self.assertTrue(self.det.update('10.0.0.2', 4000))


if __name__ == '__main__':
    unittest.main()
