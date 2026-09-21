import os
from pathlib import Path
import subprocess
import sys
import unittest

from ants import bfs_distances, format_solution, parse_anthill_text, solution_stats
from _checks import assert_valid_solution, count_oscillations

ROOT = Path(__file__).resolve().parents[1]


def solve(text):
    anthill = parse_anthill_text(text)
    return anthill, anthill.solve()


class SubjectExampleTests(unittest.TestCase):
    def test_subject_simple_case(self):
        anthill, solution = solve("3\nSv-S1\nSv-S2\nS1-Sd\nS2-Sd\n")
        self.assertEqual(solution.turns, 3)
        assert_valid_solution(self, anthill, solution)
        text = format_solution(solution)
        self.assertTrue(text.startswith("+++ E1 +++\nf1 - Sv - S1\nf2 - Sv - S2\n+++ E2 +++"))

    def test_bfs_matches_networkx(self):
        import networkx as nx

        anthill = parse_anthill_text("5\nSv-S1\nS1-S2\nS2-S3\nS3-Sd\nSv-S4\nS4-S3\n")
        self.assertEqual(bfs_distances(anthill.graph, "Sv"), nx.single_source_shortest_path_length(anthill.graph, "Sv"))


class CapacityTests(unittest.TestCase):
    def test_single_capacity_pipeline(self):
        # file indienne : d + F - 1
        anthill, solution = solve("3\nSv-S1\nS1-Sd\n")
        self.assertEqual(solution.turns, 4)
        assert_valid_solution(self, anthill, solution)

    def test_capacity_two(self):
        anthill, solution = solve("3\nSv-S1{2}\nS1-Sd\n")
        self.assertEqual(solution.turns, 3)
        assert_valid_solution(self, anthill, solution)

    def test_big_capacity_reaches_lower_bound(self):
        anthill, solution = solve("F=100\nSv - S1 { 100 }\nS1 - S2 { 100 }\nS2 - Sd\n")
        self.assertEqual(solution.lower_bound, 3)
        self.assertEqual(solution.turns, 3)
        assert_valid_solution(self, anthill, solution)

    def test_bottleneck_capacity_governs(self):
        # une salle de capacité 1 au milieu de salles énormes impose une fourmi par étape
        anthill, solution = solve("F=20\nSv - S1 {50}\nS1 - S2\nS2 - S3 {50}\nS3 - Sd\n")
        self.assertEqual(solution.turns, 4 + 20 - 1)
        assert_valid_solution(self, anthill, solution)

    def test_f100_with_spaces_in_capacities(self):
        text = "F = 100\nS1 { 5 }\nS2 { 5 }\nS3 { 10 }\nSv - S1\nSv - S2\nS1 - S3\nS2 - S3\nS3 - Sd\n"
        anthill, solution = solve(text)
        self.assertEqual(anthill.ant_count, 100)
        # S3 laisse passer au plus 10 fourmis par étape : 100 fourmis -> 10 vagues
        self.assertEqual(solution.turns, 3 + 10 - 1)
        assert_valid_solution(self, anthill, solution)


class SimultaneityTests(unittest.TestCase):
    def test_enter_while_occupant_leaves(self):
        anthill, solution = solve("3\nSv-S1\nS1-S2\nS2-Sd\n")
        self.assertEqual(solution.turns, 5)
        assert_valid_solution(self, anthill, solution)
        relay = any(
            {o for _, o, _ in moves} & {d for _, _, d in moves} - {"Sv", "Sd"}
            for moves in solution.steps
        )
        self.assertTrue(relay, "une fourmi doit entrer dans une salle au moment où l'occupante la quitte")

    def test_parallel_paths_are_used_together(self):
        anthill, solution = solve("4\nSv-S1\nSv-S2\nS1-Sd\nS2-Sd\n")
        self.assertEqual(solution.turns, 3)
        self.assertEqual(len(solution.steps[0]), 2)  # deux départs simultanés dès E1


class TopologyTests(unittest.TestCase):
    def test_direct_tunnel(self):
        for f in (1, 10, 100):
            with self.subTest(f=f):
                anthill, solution = solve(f"{f}\nSv-S1\nS1-Sd\nSd-Sv\n")
                self.assertEqual(solution.turns, 1)
                self.assertTrue(all(path == ["Sv", "Sd"] for path in solution.trajectories.values()))

    def test_dead_end_is_ignored(self):
        anthill, solution = solve("4\nSv-S1\nS1-S2\nS2-S3\nS1-Sd\n")
        self.assertEqual(solution.turns, 1 + 4)
        assert_valid_solution(self, anthill, solution)
        visited = {room for path in solution.trajectories.values() for room in path}
        self.assertNotIn("S2", visited)
        self.assertNotIn("S3", visited)

    def test_cycle_does_not_trap_ants(self):
        anthill, solution = solve("3\nSv-S1\nS1-S2\nS2-S3\nS3-S1\nS3-Sd\nS2-Sd\n")
        assert_valid_solution(self, anthill, solution)
        for path in solution.trajectories.values():
            rooms = [r for i, r in enumerate(path) if i == 0 or r != path[i - 1]]
            self.assertEqual(len(rooms), len(set(rooms)), f"boucle inutile : {path}")

    def test_isolated_room_is_harmless(self):
        anthill, solution = solve("2\nS7 {3}\nSv-S1\nS1-Sd\n")
        self.assertIn("S7", anthill.graph)
        self.assertEqual(solution.turns, 3)

    def test_tunnel_order_does_not_matter(self):
        lines = ["Sv-S1", "S1-S2{2}", "S2-Sd", "Sv-S3", "S3-Sd", "S1-S3"]
        _, forward = solve("6\n" + "\n".join(lines))
        _, backward = solve("6\n" + "\n".join(reversed(lines)))
        self.assertEqual(forward.turns, backward.turns)


class TrajectoryQualityTests(unittest.TestCase):
    def test_waiting_preferred_to_useless_back_and_forth(self):
        # l'ancien coût préférait Sv -> S1 -> Sv -> S1 à une simple attente
        anthill, solution = solve("3\nSv-S1{2}\nS1-S2\nS2-Sd\n")
        assert_valid_solution(self, anthill, solution)
        self.assertEqual(count_oscillations(solution), 0)
        self.assertEqual(solution.move_count(), 3 * 3)  # chaque fourmi fait exactement d = 3 pas

    def test_no_move_away_from_sink_when_not_needed(self):
        anthill, solution = solve("5\nSv-S1{3}\nS1-S2\nS2-Sd\nS1-S3\nS3-S4\n")
        dist = bfs_distances(anthill.graph, "Sd")
        for path in solution.trajectories.values():
            for before, after in zip(path, path[1:]):
                if before != after:
                    self.assertLess(dist[after], dist[before], path)

    def test_earliest_arrivals_at_fixed_horizon(self):
        # deux chemins de longueurs 2 et 4 : le plus court sert en priorité
        anthill, solution = solve("3\nSv-S1\nS1-Sd\nSv-S2\nS2-S3\nS3-S4\nS4-Sd\n")
        arrivals = sorted(solution.arrival_times().values())
        self.assertEqual(solution.turns, 4)
        self.assertEqual(arrivals, [2, 3, 4])

    def test_ants_numbered_by_departure(self):
        _, solution = solve("5\nSv-S1\nS1-Sd\n")
        departures = [next(t for t, r in enumerate(p) if r != "Sv") for p in solution.trajectories.values()]
        self.assertEqual(departures, sorted(departures))

    def test_solution_is_deterministic(self):
        text = (ROOT / "inputs" / "officiels" / "fourmiliere_cinq.txt").read_text(encoding="utf-8")
        _, first = solve(text)
        _, second = solve(text)
        self.assertEqual(first.trajectories, second.trajectories)

    def test_solution_is_reproducible_across_processes(self):
        code = (
            "from ants import load_anthill, format_solution;"
            "a = load_anthill('inputs/officiels/fourmiliere_3D.txt');"
            "print(format_solution(a.solve()))"
        )
        outputs = set()
        for seed in ("1", "2", "3"):
            env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONIOENCODING="utf-8")
            result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, check=True)
            outputs.add(result.stdout)
        self.assertEqual(len(outputs), 1)


class OptimalityTests(unittest.TestCase):
    def test_horizon_below_optimum_is_infeasible(self):
        anthill, solution = solve("f=10\nS1 { 2 }\nS2\nS3\nS4 { 2 }\nS5\nS6\nS3 - S4\nSv - S1\nS1 - S2\nS2 - S4\nS4 - S5\nS5 - Sd\nS4 - S6\nS6 - Sd\nS1 - S3\n")
        self.assertLess(anthill.max_ants_within(solution.turns - 1), anthill.ant_count)
        self.assertEqual(anthill.max_ants_within(solution.turns), anthill.ant_count)
        self.assertGreaterEqual(solution.turns, solution.lower_bound)

    def test_horizon_flows_are_monotone(self):
        _, solution = solve("f=12\nSv-S1{2}\nS1-S2\nS2-Sd\nSv-S3\nS3-S4{3}\nS4-Sd\n")
        flows = [f for _, f in solution.horizon_flows]
        self.assertEqual(flows, sorted(flows))
        self.assertEqual(flows[-1], 12)
        self.assertTrue(all(f < 12 for f in flows[:-1]))

    def test_stats(self):
        anthill, solution = solve("3\nSv-S1\nSv-S2\nS1-Sd\nS2-Sd\nS1-S2\n")
        stats = solution_stats(anthill, solution)
        self.assertEqual(stats["tunnels"], 5)
        self.assertEqual(stats["tunnels_utilises"] + stats["tunnels_jamais_utilises"], 5)
        self.assertEqual(stats["mouvements_total"], 6)
        self.assertEqual(stats["etapes_optimales_T"], 3)


if __name__ == "__main__":
    unittest.main()
