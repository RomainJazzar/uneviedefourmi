"""Contre-exemple pédagogique : plus court chemin individuel ≠ temps minimum de la colonie.

inputs/demo/plus_court_chemin_vs_trafic.txt, 3 fourmis, capacité 1 partout :
    chemin A : Sv -> S1 -> Sd        (longueur 2, le plus court)
    chemin B : Sv -> S2 -> S3 -> Sd  (longueur 3)

La stratégie « plus court chemin uniquement » est simulée ICI, dans les tests,
comme référence pédagogique. Ce n'est pas un algorithme du projet.
"""

from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest

import networkx as nx

from ants import bfs_distances, load_anthill
from _checks import assert_valid_solution

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "inputs" / "demo" / "plus_court_chemin_vs_trafic.txt"


def shortest_path_only_schedule(anthill):
    """Toutes les fourmis suivent UN plus court chemin, en file indienne.

    À chaque étape, on fait avancer les fourmis en partant de la plus proche de
    Sd : une fourmi avance si la salle suivante a encore de la place à la fin de
    l'étape (Sd n'est jamais pleine). Retourne la liste des étapes.
    """
    path = nx.shortest_path(anthill.graph, "Sv", "Sd")
    position = {f"f{i}": 0 for i in range(1, anthill.ant_count + 1)}  # indice dans path
    steps = []
    while any(p < len(path) - 1 for p in position.values()):
        occupancy = Counter(path[p] for p in position.values())
        moves = []
        for ant in sorted(position, key=lambda a: (-position[a], int(a[1:]))):
            here = position[ant]
            if here == len(path) - 1:
                continue
            nxt = path[here + 1]
            if nxt == "Sd" or occupancy[nxt] < anthill.room_capacity(nxt):
                occupancy[path[here]] -= 1
                occupancy[nxt] += 1
                position[ant] = here + 1
                moves.append((ant, path[here], nxt))
        steps.append(sorted(moves, key=lambda m: int(m[0][1:])))
    return path, steps


class ShortestPathVersusFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.anthill = load_anthill(DEMO)
        cls.solution = cls.anthill.solve()

    def test_bfs_distance_is_two(self):
        self.assertEqual(bfs_distances(self.anthill.graph, "Sv")["Sd"], 2)
        self.assertEqual(self.solution.lower_bound, 2)

    def test_shortest_path_only_takes_four_steps(self):
        path, steps = shortest_path_only_schedule(self.anthill)
        self.assertEqual(path, ["Sv", "S1", "Sd"])
        self.assertEqual(len(steps), 4)
        self.assertEqual(
            steps,
            [
                [("f1", "Sv", "S1")],
                [("f1", "S1", "Sd"), ("f2", "Sv", "S1")],
                [("f2", "S1", "Sd"), ("f3", "Sv", "S1")],
                [("f3", "S1", "Sd")],
            ],
        )

    def test_real_solver_takes_three_steps(self):
        self.assertEqual(self.solution.turns, 3)
        assert_valid_solution(self, self.anthill, self.solution)  # capacités, tunnels, tout le monde dans Sd
        self.assertTrue(all(path[-1] == "Sd" for path in self.solution.trajectories.values()))

    def test_real_solver_uses_both_paths(self):
        used = {frozenset((a, b)) for moves in self.solution.steps for _, a, b in moves}
        self.assertIn(frozenset(("S1", "Sd")), used)
        self.assertIn(frozenset(("S3", "Sd")), used)
        self.assertEqual(
            self.solution.steps,
            [
                [("f1", "Sv", "S1"), ("f2", "Sv", "S2")],
                [("f1", "S1", "Sd"), ("f2", "S2", "S3"), ("f3", "Sv", "S1")],
                [("f2", "S3", "Sd"), ("f3", "S1", "Sd")],
            ],
        )

    def test_demo_tool_matches_and_draws(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import demo_algorithmes

        with tempfile.TemporaryDirectory() as tmp:
            result = demo_algorithmes.run(DEMO, Path(tmp))
            self.assertEqual(result, {"d": 2, "plus_court_chemin": 4, "max_flow": 3})
            self.assertTrue((Path(tmp) / "shortest_path_vs_flow.png").stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
