"""Vérification indépendante de l'optimalité par exploration exhaustive.

Ce solveur de référence n'existe QUE dans les tests. Il simule directement
les règles du sujet sur l'espace des configurations globales (combien de
fourmis dans chaque salle), sans graphe temporel ni flot :

- à chaque étape, chaque fourmi attend ou prend un tunnel ;
- une configuration est valide si aucune salle intermédiaire ne dépasse sa
  capacité à la fin de l'étape (une fourmi peut donc entrer pendant que
  l'occupante sort) ;
- les fourmis peuvent même ressortir de Sd : la référence ne suppose pas que
  le dortoir est absorbant.

Un BFS sur ces configurations donne le véritable nombre minimal d'étapes.
Son coût explose avec F et le nombre de salles : il est inutilisable en
production, mais parfait pour contrôler de petits cas.
"""

from __future__ import annotations

from collections import deque
from functools import lru_cache
import heapq
from itertools import product
from pathlib import Path
import random
import re
import unittest

from ants import load_anthill, parse_anthill_text
from _checks import assert_valid_solution

OFFICIAL_DIR = Path(__file__).resolve().parents[1] / "inputs" / "officiels"


@lru_cache(maxsize=None)
def _compositions(total: int, parts: int) -> tuple:
    """Toutes les façons de répartir `total` fourmis identiques entre `parts` choix."""
    if parts == 1:
        return ((total,),)
    return tuple((k,) + rest for k in range(total + 1) for rest in _compositions(total - k, parts - 1))


class Reference:
    """Solveur exhaustif construit directement depuis la spécification brute
    (salles, tunnels, capacités explicites), sans passer par le modèle Anthill."""

    def __init__(self, ant_count: int, tunnels, explicit_caps: dict, rooms=()):
        names = {"Sv", "Sd"} | set(rooms) | {r for t in tunnels for r in t}
        self.rooms = ["Sv"] + sorted(names - {"Sv", "Sd"}) + ["Sd"]
        self.index = {r: i for i, r in enumerate(self.rooms)}
        self.f = ant_count
        # règle du sujet : 1 par défaut, X pour SN{X}, Sv/Sd non limités
        self.caps = [ant_count if r in ("Sv", "Sd") else explicit_caps.get(r, 1) for r in self.rooms]
        neighbours = {r: set() for r in self.rooms}
        for a, b in tunnels:
            neighbours[a].add(b)
            neighbours[b].add(a)
        self.options = [[i] + sorted(self.index[n] for n in neighbours[r]) for i, r in enumerate(self.rooms)]
        self.sv, self.sd = self.index["Sv"], self.index["Sd"]
        self.start = tuple(self.f if i == self.sv else 0 for i in range(len(self.rooms)))
        self.goal = tuple(self.f if i == self.sd else 0 for i in range(len(self.rooms)))

    def successors(self, state):
        """(configuration suivante, nombre de fourmis qui ont bougé)."""
        per_room = []
        for i, count in enumerate(state):
            if count == 0:
                continue
            opts = self.options[i]
            per_room.append([(i, opts, comp) for comp in _compositions(count, len(opts))])
        for combo in product(*per_room):
            new = [0] * len(state)
            moved = 0
            for i, opts, comp in combo:
                for dest, k in zip(opts, comp):
                    new[dest] += k
                    if dest != i:
                        moved += k
            if all(n <= c for n, c in zip(new, self.caps)):
                yield tuple(new), moved

    def min_steps(self) -> int:
        seen = {self.start: 0}
        queue = deque([self.start])
        while queue:
            state = queue.popleft()
            if state == self.goal:
                return seen[state]
            for nxt, _ in self.successors(state):
                if nxt not in seen:
                    seen[nxt] = seen[state] + 1
                    queue.append(nxt)
        raise AssertionError("aucune solution")

    def best_secondary(self, horizon: int) -> tuple[int, int]:
        """Minimum lexicographique (somme des dates d'arrivée, mouvements) en <= horizon étapes."""
        heap = [((0, 0), 0, self.start)]
        best = {}
        while heap:
            cost, t, state = heapq.heappop(heap)
            if state == self.goal:
                return cost
            if best.get((state, t), (float("inf"),)) < cost or t == horizon:
                continue
            outside = self.f - state[self.sd]
            for nxt, moved in self.successors(state):
                new_cost = (cost[0] + outside, cost[1] + moved)
                if new_cost < best.get((nxt, t + 1), (float("inf"), float("inf"))):
                    best[(nxt, t + 1)] = new_cost
                    heapq.heappush(heap, (new_cost, t + 1, nxt))
        raise AssertionError("aucune solution dans l'horizon")


def random_anthill(rng: random.Random):
    """Petite fourmilière aléatoire : (texte aux syntaxes variées, Reference)."""
    n = rng.randint(1, 5)
    f = rng.randint(1, 3)
    rooms = ["Sv"] + [f"S{i}" for i in range(1, n + 1)] + ["Sd"]
    lines = [rng.choice(["{f}", "f={f}", "F = {f}", "fourmis: {f}"]).format(f=f)]
    caps = {}
    for room in rooms[1:-1]:
        cap = rng.choice([None, None, 1, 2, 3])
        if cap is not None:
            caps[room] = cap
            lines.append(rng.choice(["{r}{{{c}}}", "{r} {{ {c} }}", "{r}   {{{c} }}"]).format(r=room, c=cap))
        elif rng.random() < 0.5:
            lines.append(room)
    density = rng.uniform(0.25, 0.7)
    tunnels = [
        (a, b)
        for i, a in enumerate(rooms)
        for b in rooms[i + 1:]
        if rng.random() < (density if {a, b} != {"Sv", "Sd"} else 0.08)
    ]
    rng.shuffle(tunnels)
    for a, b in tunnels:
        if rng.random() < 0.5:
            a, b = b, a
        lines.append(rng.choice(["{a} - {b}", "{a}-{b}", "{a}  -   {b}"]).format(a=a, b=b))
    return "\n".join(lines) + "\n", Reference(f, tunnels, caps, rooms)


def reference_from_text(text: str) -> Reference:
    """Lecture minimale et indépendante (pour les cas écrits à la main et les petits
    fichiers officiels) : première ligne = F, puis « S1 {2} » ou « A - B »."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    f = int(re.sub(r"\D", "", lines[0]))
    tunnels, caps, rooms = [], {}, set()
    for line in lines[1:]:
        for token in line.split("-"):
            name = token.split("{")[0].strip()
            rooms.add(name)
            if "{" in token:
                caps[name] = int(token.split("{")[1].split("}")[0])
        if "-" in line:
            a, b = (t.split("{")[0].strip() for t in line.split("-"))
            tunnels.append((a, b))
    return Reference(f, tunnels, caps, rooms)


def random_cases(seed: int, count: int):
    rng = random.Random(seed)
    produced = 0
    while produced < count:
        text, reference = random_anthill(rng)
        try:
            anthill = parse_anthill_text(text)
        except ValueError:
            continue  # pas de chemin Sv -> Sd : on tire un autre graphe
        produced += 1
        yield text, anthill, reference


class BruteForceComparisonTests(unittest.TestCase):
    def test_min_steps_matches_exhaustive_bfs(self):
        checked = 0
        for text, anthill, reference in random_cases(seed=20260921, count=400):
            with self.subTest(case=text):
                expected = reference.min_steps()
                solution = anthill.solve()
                self.assertEqual(solution.turns, expected)
                assert_valid_solution(self, anthill, solution)
                checked += 1
        self.assertEqual(checked, 400)

    def test_secondary_objectives_match_exhaustive_search(self):
        # à T optimal : arrivées au plus tôt, puis nombre minimal de mouvements
        for text, anthill, reference in random_cases(seed=1789, count=150):
            with self.subTest(case=text):
                solution = anthill.solve()
                expected = reference.best_secondary(solution.turns)
                got = (sum(solution.arrival_times().values()), solution.move_count())
                self.assertEqual(got, expected)

    def test_hand_made_tricky_cases(self):
        cases = [
            "3\nSv-S1\nS1-S2\nS2-Sd\nSv-S3\nS3-S2\n",          # convergence sur S2
            "3\nSv-S1{2}\nS1-S2\nS2-S3\nS3-S1\nS3-Sd\n",       # cycle
            "3\nSv-S1\nS1-Sd\nS1-S2\nS2-S3\n",                 # cul-de-sac
            "3\nSv-S1\nS1-S2\nS2-Sd\nSd-Sv\n",                 # tunnel direct
            "4\nSv-S1{3}\nS1-S2\nS2-Sd\nS1-S3\nS3-S4\nS4-Sd\n",  # chemin court étroit / long large
            "3\nSv-S1\nS1-S2{2}\nS2-S3\nS3-Sd\nS2-S4\nS4-Sd\n",
        ]
        for text in cases:
            with self.subTest(case=text):
                anthill = parse_anthill_text(text)
                self.assertEqual(anthill.solve().turns, reference_from_text(text).min_steps())

    def test_small_official_files(self):
        for name in ["fourmiliere_zero.txt", "fourmiliere_un.txt", "fourmiliere_deux.txt", "fourmiliere_trois.txt"]:
            with self.subTest(name=name):
                text = (OFFICIAL_DIR / name).read_text(encoding="utf-8")
                anthill = load_anthill(OFFICIAL_DIR / name)
                self.assertEqual(anthill.solve().turns, reference_from_text(text).min_steps())


if __name__ == "__main__":
    unittest.main()
