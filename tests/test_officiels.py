"""Non-régression sur les 9 fourmilières officielles.

Les valeurs attendues ne sont PAS utilisées par le solveur : elles servent
uniquement de contrôle. Elles ont été confirmées indépendamment
(borne basse BFS, max-flow à T-1 insuffisant, et BFS exhaustif sur les petits cas).
"""

from pathlib import Path
import unittest

from ants import SINK, SOURCE, bfs_distances, load_anthill
from _checks import assert_valid_solution, count_oscillations

OFFICIAL_DIR = Path(__file__).resolve().parents[1] / "inputs" / "officiels"

# fichier -> (F, T optimal attendu)
EXPECTED = {
    "fourmiliere_zero.txt": (2, 2),
    "fourmiliere_un.txt": (5, 7),
    "fourmiliere_deux.txt": (5, 1),
    "fourmiliere_trois.txt": (5, 7),
    "fourmiliere_quatre.txt": (10, 9),
    "fourmiliere_cinq.txt": (50, 11),
    "fourmiliere_3D.txt": (50, 14),
    "La_hormiguera_de_la_muerte.txt": (30, 9),
    "salle_d_at-ant.txt": (100, 15),
}


class OfficialAnthillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {}
        for name in EXPECTED:
            anthill = load_anthill(OFFICIAL_DIR / name)
            cls.results[name] = (anthill, anthill.solve())

    def test_all_nine_files_present(self):
        self.assertEqual(sorted(p.name for p in OFFICIAL_DIR.glob("*.txt")), sorted(EXPECTED))

    def test_parsed_with_source_sink_and_path(self):
        for name, (anthill, _) in self.results.items():
            with self.subTest(name=name):
                self.assertEqual(anthill.ant_count, EXPECTED[name][0])
                self.assertIn(SOURCE, anthill.graph)
                self.assertIn(SINK, anthill.graph)
                self.assertIn(SINK, bfs_distances(anthill.graph, SOURCE))

    def test_solutions_respect_every_rule(self):
        for name, (anthill, solution) in self.results.items():
            with self.subTest(name=name):
                assert_valid_solution(self, anthill, solution)
                anthill._validate_solution(solution.trajectories, solution.turns)

    def test_optimal_number_of_steps(self):
        for name, (anthill, solution) in self.results.items():
            with self.subTest(name=name):
                self.assertEqual(solution.turns, EXPECTED[name][1])
                self.assertGreaterEqual(solution.turns, solution.lower_bound)
                # preuve de minimalité : avec une étape de moins, le max-flow est insuffisant
                if solution.turns > solution.lower_bound:
                    self.assertLess(anthill.max_ants_within(solution.turns - 1), anthill.ant_count)

    def test_no_back_and_forth(self):
        for name, (_, solution) in self.results.items():
            with self.subTest(name=name):
                self.assertEqual(count_oscillations(solution), 0)

    def test_direct_tunnel_in_fourmiliere_deux(self):
        anthill, solution = self.results["fourmiliere_deux.txt"]
        self.assertTrue(anthill.graph.has_edge("Sv", "Sd"))
        self.assertEqual(solution.turns, 1)
        self.assertTrue(all(p == ["Sv", "Sd"] for p in solution.trajectories.values()))

    def test_capacities_parsed_from_spaced_syntax(self):
        anthill, _ = self.results["salle_d_at-ant.txt"]
        self.assertEqual(anthill.room_capacity("S1"), 50)
        self.assertEqual(anthill.room_capacity("S4"), 1)
        self.assertEqual(anthill.room_capacity("S21"), 30)
        anthill, _ = self.results["fourmiliere_cinq.txt"]
        self.assertEqual(anthill.room_capacity("S9"), 1)  # « S9 » avec espace final
        self.assertEqual(anthill.room_capacity("S13"), 4)


if __name__ == "__main__":
    unittest.main()
