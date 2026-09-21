"""Une vie de fourmi : modèle, lecture des fichiers et résolution optimale.

Vue d'ensemble de l'algorithme (détaillé dans le README) :

1. BFS sur le graphe des salles  -> distance minimale d entre Sv et Sd
   (aucune fourmi ne peut arriver avant d étapes : c'est la borne basse).
2. Pour un horizon T, on « déplie » la fourmilière dans le temps
   (time-expanded network) : une copie de chaque salle par instant 0..T.
3. Chaque salle est coupée en entrée -> sortie avec une capacité égale à
   la capacité de la salle (node splitting) : c'est ce qui applique SN{X}.
4. Un max-flow (Edmonds-Karp) répond à la question « F fourmis peuvent-elles
   arriver en T étapes ? ». On teste T = d, d+1, ... : le premier T faisable
   est le minimum.
5. À T fixé, un flot de coût minimal choisit, parmi toutes les solutions
   optimales, la plus lisible (arrivées au plus tôt, puis le moins de
   mouvements, puis le moins de pas qui n'avancent pas vers Sd).
6. Le flot entier est découpé en trajectoires individuelles f1, f2, ...
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, Hashable, Iterable, List, Tuple

import networkx as nx

SOURCE = "Sv"
SINK = "Sd"

Trajectories = Dict[str, List[str]]
Move = Tuple[str, str, str]


class AnthillFormatError(ValueError):
    """Erreur de lecture d'un fichier de fourmilière (avec numéro de ligne)."""

    def __init__(self, message: str, line_number: int | None = None, line: str | None = None):
        self.line_number = line_number
        self.line = line
        if line_number is not None:
            message = f"ligne {line_number} : {message}"
            if line is not None:
                message += f"  ->  {line!r}"
        super().__init__(message)


@dataclass
class Solution:
    """Résultat complet d'une résolution."""

    turns: int
    trajectories: Trajectories
    steps: List[List[Move]]
    lower_bound: int = 0
    # (T testé, nombre maximal de fourmis pouvant arriver en T étapes)
    horizon_flows: List[Tuple[int, int]] = field(default_factory=list)

    def arrival_times(self) -> Dict[str, int]:
        return {ant: path.index(SINK) for ant, path in self.trajectories.items()}

    def move_count(self) -> int:
        return sum(len(moves) for moves in self.steps)


# ---------------------------------------------------------------------------
# Modèle
# ---------------------------------------------------------------------------


class Anthill:
    """Fourmilière = graphe non orienté (salle = sommet, tunnel = arête)."""

    def __init__(self, ant_count: int) -> None:
        if ant_count < 1:
            raise ValueError("Le nombre de fourmis doit être un entier >= 1.")
        self.ant_count = ant_count
        self.graph = nx.Graph()
        self.graph.add_nodes_from([SOURCE, SINK])
        # Capacités explicitement données (SN{X}) ; les autres valent 1.
        self.explicit_capacities: Dict[str, int] = {}
        self.warnings: List[str] = []

    # -- construction -------------------------------------------------------

    def add_room(self, room: str, capacity: int | None = None) -> None:
        room = room.strip()
        if not room:
            raise ValueError("Nom de salle vide.")
        self.graph.add_node(room)
        if capacity is None:
            return
        if capacity < 1:
            raise ValueError(f"Capacité invalide pour {room} : {capacity} (doit être >= 1).")
        if room in (SOURCE, SINK):
            self.warnings.append(
                f"Capacité {capacity} ignorée pour {room} : le vestibule et le dortoir "
                "ne sont pas limités."
            )
            return
        previous = self.explicit_capacities.get(room)
        if previous is not None and previous != capacity:
            raise ValueError(
                f"Capacités contradictoires pour {room} : {previous} puis {capacity}."
            )
        self.explicit_capacities[room] = capacity

    def add_tunnel(self, room_a: str, room_b: str) -> None:
        if room_a == room_b:
            raise ValueError(f"Un tunnel ne peut pas relier {room_a} à elle-même.")
        self.add_room(room_a)
        self.add_room(room_b)
        self.graph.add_edge(room_a, room_b)

    # -- lecture ------------------------------------------------------------

    def room_capacity(self, room: str) -> int:
        """Sv et Sd ne limitent jamais : capacité F. Sinon SN{X} ou 1 par défaut."""
        if room in (SOURCE, SINK):
            return self.ant_count
        return self.explicit_capacities.get(room, 1)

    @property
    def rooms(self) -> List[str]:
        """Toutes les salles, dans un ordre stable (Sv, S1, S2, ..., Sd)."""
        return sorted(self.graph.nodes, key=room_sort_key)

    @property
    def intermediate_rooms(self) -> List[str]:
        return [r for r in self.rooms if r not in (SOURCE, SINK)]

    @property
    def tunnels(self) -> List[Tuple[str, str]]:
        """Tunnels dans un ordre stable, chaque tunnel une seule fois."""
        edges = [tuple(sorted(e, key=room_sort_key)) for e in self.graph.edges]
        return sorted(edges, key=lambda e: (room_sort_key(e[0]), room_sort_key(e[1])))

    def adjacency_matrix(self) -> tuple[list[str], list[list[int]]]:
        nodes = self.rooms
        index = {n: i for i, n in enumerate(nodes)}
        matrix = [[0] * len(nodes) for _ in nodes]
        for u, v in self.graph.edges:
            matrix[index[u]][index[v]] = matrix[index[v]][index[u]] = 1
        return nodes, matrix

    def validate(self) -> None:
        if SOURCE not in self.graph or SINK not in self.graph:
            raise ValueError("La fourmilière doit contenir Sv et Sd.")
        if SINK not in bfs_distances(self.graph, SOURCE):
            raise ValueError("Aucun chemin ne relie Sv à Sd.")

    # -- résolution ---------------------------------------------------------

    def shortest_distance(self) -> int:
        """Borne basse d : longueur du plus court chemin Sv -> Sd (BFS)."""
        self.validate()
        return bfs_distances(self.graph, SOURCE)[SINK]

    def max_ants_within(self, horizon: int) -> int:
        """Nombre maximal de fourmis pouvant atteindre Sd en `horizon` étapes (max-flow)."""
        expanded = self._build_time_expanded_graph(horizon, with_costs=False)
        return nx.maximum_flow_value(
            expanded,
            (SOURCE, 0, "in"),
            (SINK, horizon, "out"),
            capacity="capacity",
            flow_func=nx.algorithms.flow.edmonds_karp,
        )

    def throughput_bottleneck(self) -> Tuple[int | None, List[str]]:
        """Débit maximal par étape et salles qui le limitent (coupe minimale).

        Max-flow « statique » (sans le temps) sur le graphe à salles dédoublées :
        il indique combien de fourmis peuvent arriver par étape en régime
        établi, et la coupe minimale désigne le goulot d'étranglement.
        Avec un tunnel direct Sv-Sd, le débit est illimité : (None, []).
        """
        if self.graph.has_edge(SOURCE, SINK):
            return None, []
        g = nx.DiGraph()
        for room in self._active_rooms():
            if room in (SOURCE, SINK):
                g.add_edge((room, "in"), (room, "out"))  # capacité infinie
            else:
                g.add_edge((room, "in"), (room, "out"), capacity=self.room_capacity(room))
        for u, v in self.tunnels:
            if (u, "in") in g and (v, "in") in g:
                g.add_edge((u, "out"), (v, "in"))
                g.add_edge((v, "out"), (u, "in"))
        value, (reachable, _) = nx.minimum_cut(g, (SOURCE, "out"), (SINK, "in"))
        cut = [r for r in self.intermediate_rooms if (r, "in") in reachable and (r, "out") in g and (r, "out") not in reachable]
        return int(value), cut

    def solve(self) -> Solution:
        """Trouve un ordonnancement avec le nombre minimal d'étapes."""
        lower = self.shortest_distance()
        # Borne haute sûre : en file indienne sur un plus court chemin, une
        # fourmi part à chaque étape, la dernière arrive donc en d + F - 1.
        upper = lower + self.ant_count - 1

        horizon_flows: List[Tuple[int, int]] = []
        best: int | None = None
        # Recherche linéaire : le premier T faisable est l'optimum. (Une
        # recherche binaire serait valide car la faisabilité est monotone,
        # mais le benchmark montre qu'elle n'apporte rien ici.)
        for horizon in range(lower, upper + 1):
            flow = self.max_ants_within(horizon)
            horizon_flows.append((horizon, flow))
            if flow >= self.ant_count:
                best = horizon
                break
        if best is None:  # impossible si la borne haute est juste
            raise RuntimeError("Aucune solution trouvée malgré l'existence d'un chemin.")

        cost_graph = self._build_time_expanded_graph(best, with_costs=True)
        flow_dict = nx.min_cost_flow(cost_graph, demand="demand", capacity="capacity", weight="weight")
        trajectories = self._decompose_flow(flow_dict, best)
        self._validate_solution(trajectories, best)
        steps = trajectories_to_steps(trajectories, best)
        return Solution(best, trajectories, steps, lower, horizon_flows)

    def _active_rooms(self) -> List[str]:
        """Salles accessibles depuis Sv (les autres ne servent à rien)."""
        reachable = bfs_distances(self.graph, SOURCE)
        return [r for r in self.rooms if r in reachable]

    def _build_time_expanded_graph(self, horizon: int, with_costs: bool) -> nx.DiGraph:
        """
        Graphe temporel pour un horizon T.

        - (salle, t, "in") -> (salle, t, "out") : capacité de la salle ;
        - (salle, t, "out") -> (salle, t+1, "in") : attendre ;
        - (a, t, "out") -> (b, t+1, "in") : traverser le tunnel a-b.

        Sd est absorbant : aucun arc ne sort du dortoir vers une autre salle
        (cela ne change pas le T optimal : une fourmi arrivée peut toujours
        rester au dortoir, qui n'est pas limité).
        """
        f = self.ant_count
        rooms = self._active_rooms()
        to_sink = bfs_distances(self.graph, SINK)
        weights = _lexicographic_weights(f, horizon)

        g = nx.DiGraph()
        for t in range(horizon + 1):
            for room in rooms:
                g.add_node((room, t, "in"), demand=0)
                g.add_node((room, t, "out"), demand=0)
                g.add_edge((room, t, "in"), (room, t, "out"), capacity=self.room_capacity(room), weight=0)
        if with_costs:
            g.nodes[(SOURCE, 0, "in")]["demand"] = -f
            g.nodes[(SINK, horizon, "out")]["demand"] = f

        for t in range(horizon):
            for room in rooms:
                g.add_edge(
                    (room, t, "out"),
                    (room, t + 1, "in"),
                    capacity=self.room_capacity(room),
                    weight=_transition_cost(room, room, to_sink, weights) if with_costs else 0,
                )
            for u, v in self.tunnels:
                if u not in to_sink or v not in to_sink:
                    continue
                for origin, dest in ((u, v), (v, u)):
                    if origin == SINK:
                        continue  # Sd absorbant
                    g.add_edge(
                        (origin, t, "out"),
                        (dest, t + 1, "in"),
                        capacity=f,  # le sujet ne limite pas les tunnels
                        weight=_transition_cost(origin, dest, to_sink, weights) if with_costs else 0,
                    )
        return g

    def _decompose_flow(self, flow: Dict, horizon: int) -> Trajectories:
        """Découpe le flot entier en F trajectoires (une par fourmi)."""
        remaining: Dict[Hashable, Dict[Hashable, int]] = {
            u: {v: int(value) for v, value in nbrs.items() if value}
            for u, nbrs in flow.items()
        }
        start, end = (SOURCE, 0, "in"), (SINK, horizon, "out")
        paths: List[List[str]] = []
        for _ in range(self.ant_count):
            node = start
            rooms_by_time: List[str] = [SOURCE]
            while node != end:
                candidates = sorted(
                    (v for v, value in remaining.get(node, {}).items() if value > 0),
                    key=lambda n: (n[1], room_sort_key(n[0]), n[2]),
                )
                if not candidates:
                    raise RuntimeError("Impossible de décomposer le flot en trajectoires.")
                nxt = candidates[0]
                remaining[node][nxt] -= 1
                if nxt[2] == "in" and nxt[1] > node[1]:
                    rooms_by_time.append(nxt[0])
                node = nxt
            paths.append(rooms_by_time)

        # Numérotation lisible : f1 est la première fourmi à partir.
        def order(path: List[str]) -> tuple:
            departure = next((t for t, r in enumerate(path) if r != SOURCE), len(path))
            return (departure, path.index(SINK), [room_sort_key(r) for r in path])

        paths.sort(key=order)
        return {f"f{i}": path for i, path in enumerate(paths, start=1)}

    def _validate_solution(self, trajectories: Trajectories, horizon: int) -> None:
        """Vérifie toutes les règles du sujet sur la solution produite."""
        if len(trajectories) != self.ant_count:
            raise AssertionError("Nombre de trajectoires incohérent.")
        for ant, path in trajectories.items():
            if len(path) != horizon + 1 or path[0] != SOURCE or path[-1] != SINK:
                raise AssertionError(f"Trajectoire invalide pour {ant} : {path}")
            for before, after in zip(path, path[1:]):
                if before != after and not self.graph.has_edge(before, after):
                    raise AssertionError(f"Déplacement impossible : {before} -> {after}")
                if before == SINK and after != SINK:
                    raise AssertionError(f"{ant} ressort du dortoir.")
        for t in range(horizon + 1):
            occupancy = Counter(path[t] for path in trajectories.values())
            for room, count in occupancy.items():
                if count > self.room_capacity(room):
                    raise AssertionError(
                        f"Capacité dépassée à t={t} : {room} contient {count} fourmis "
                        f"pour une capacité de {self.room_capacity(room)}."
                    )
        if max(path.index(SINK) for path in trajectories.values()) != horizon:
            raise AssertionError("La dernière arrivée ne correspond pas à l'horizon.")


# ---------------------------------------------------------------------------
# Coûts du min-cost flow (optimisation secondaire, T déjà fixé)
# ---------------------------------------------------------------------------


def _lexicographic_weights(ant_count: int, horizon: int) -> Tuple[int, int, int]:
    """
    Poids pour un ordre de priorité strict entre les objectifs secondaires.

    Chaque fourmi fait exactement T transitions, donc chaque objectif compte
    au plus F*T unités. Avec M = F*T + 1 :
      objectif 2 (somme des dates d'arrivée)      poids M²
      objectif 3 (nombre de mouvements)           poids M
      objectif 4 (mouvements qui n'avancent pas)  poids 1
    Une unité d'un objectif coûte plus que le maximum cumulé des suivants
    (M·F·T + F·T < M²), donc aucun objectif ne peut prendre le dessus sur
    un objectif plus prioritaire.
    """
    m = ant_count * horizon + 1
    return m * m, m, 1


def _transition_cost(origin: str, dest: str, to_sink: Dict[str, int], weights: Tuple[int, int, int]) -> int:
    w_arrival, w_move, w_detour = weights
    if origin == SINK:
        return 0  # fourmi arrivée : plus aucun coût
    cost = w_arrival  # une étape de plus passée hors du dortoir
    if origin != dest:
        cost += w_move
        if to_sink[dest] >= to_sink[origin]:
            cost += w_detour  # le pas ne rapproche pas de Sd
    return cost


# ---------------------------------------------------------------------------
# Outils de graphe
# ---------------------------------------------------------------------------


def bfs_distances(graph: nx.Graph, start: str) -> Dict[str, int]:
    """Parcours en largeur : distance (en tunnels) de `start` à chaque salle accessible.

    Le graphe n'est pas pondéré (tous les tunnels valent une étape), donc
    le BFS donne exactement les plus courts chemins.
    """
    distances = {start: 0}
    queue = deque([start])
    while queue:
        room = queue.popleft()
        for neighbour in sorted(graph.neighbors(room), key=room_sort_key):
            if neighbour not in distances:
                distances[neighbour] = distances[room] + 1
                queue.append(neighbour)
    return distances


def trajectories_to_steps(trajectories: Trajectories, horizon: int) -> List[List[Move]]:
    steps: List[List[Move]] = []
    for t in range(1, horizon + 1):
        steps.append(
            [(ant, path[t - 1], path[t]) for ant, path in trajectories.items() if path[t - 1] != path[t]]
        )
    return steps


def room_sort_key(name: str) -> tuple:
    """Ordre naturel : Sv, S1, S2, ..., S10, ..., autres noms, Sd."""
    if name == SOURCE:
        return (0, 0, 0, "")
    if name == SINK:
        return (2, 0, 0, "")
    match = re.fullmatch(r"S(\d+)", name)
    if match:
        return (1, 0, int(match.group(1)), "")
    return (1, 1, 0, name)


# compatibilité avec l'ancien nom
_room_sort_key = room_sort_key


# ---------------------------------------------------------------------------
# Lecture des fichiers
# ---------------------------------------------------------------------------

def _room_token(group: str) -> str:
    # nom (commence par une lettre) + capacité optionnelle entre accolades, espaces libres
    return rf"(?P<{group}>[^\W\d]\w*)\s*(?:\{{\s*(?P<{group}cap>\d+)\s*\}})?"


ROOM_RE = re.compile("^" + _room_token("a") + "$")
TUNNEL_RE = re.compile("^" + _room_token("a") + r"\s*[-–—]\s*" + _room_token("b") + "$")
COUNT_RE = re.compile(r"^(?:(?:f|fourmis|ants)\s*[:=]\s*)?(?P<n>[+-]?\d+)$", re.IGNORECASE)


def _canonical(name: str) -> str:
    lowered = name.lower()
    return SOURCE if lowered == "sv" else SINK if lowered == "sd" else name


def parse_room_token(token: str) -> tuple[str, int | None]:
    """Analyse « S3 », « S3{4} », « S3 { 4 } »..."""
    match = ROOM_RE.match(token.strip())
    if not match:
        raise ValueError(f"Salle mal formée : {token.strip()!r}")
    cap = match.group("acap")
    return _canonical(match.group("a")), int(cap) if cap is not None else None


def parse_anthill_text(text: str) -> Anthill:
    """
    Lit une fourmilière.

    Nombre de fourmis (première ligne utile) : « 8 », « f=8 », « F = 100 », « fourmis: 8 ».
    Salle seule : « S1 », « S1{5} », « S1 { 5 } » (espaces libres).
    Tunnel : « Sv - S1 », « Sv-S1 », « S1{3} - S2 ».
    Lignes vides, tabulations, BOM UTF-8, CRLF et commentaires « # ... » sont acceptés.
    Toute autre ligne produit une erreur avec son numéro.
    """
    text = text.lstrip("﻿")
    anthill: Anthill | None = None
    capacity_lines: Dict[str, int] = {}

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue

        count = COUNT_RE.match(line)
        if count:
            if anthill is not None:
                raise AnthillFormatError("nombre de fourmis défini deux fois", number, raw.strip())
            value = int(count.group("n"))
            if value < 1:
                raise AnthillFormatError("le nombre de fourmis doit être >= 1", number, raw.strip())
            anthill = Anthill(value)
            continue
        if anthill is None:
            raise AnthillFormatError(
                "la première ligne utile doit donner le nombre de fourmis (ex. f=10)",
                number,
                raw.strip(),
            )

        tunnel = TUNNEL_RE.match(line)
        room = ROOM_RE.match(line) if not tunnel else None
        if tunnel:
            tokens = [("a", tunnel), ("b", tunnel)]
        elif room:
            tokens = [("a", room)]
        else:
            raise AnthillFormatError("ligne non reconnue (salle « S1 {2} » ou tunnel « S1 - S2 » attendu)", number, raw.strip())

        try:
            names = []
            for group, match in tokens:
                name = _canonical(match.group(group))
                cap = match.group(group + "cap")
                if cap is not None and name in anthill.explicit_capacities and anthill.explicit_capacities[name] != int(cap):
                    raise ValueError(
                        f"capacités contradictoires pour {name} : {anthill.explicit_capacities[name]} "
                        f"(ligne {capacity_lines[name]}) puis {cap}"
                    )
                anthill.add_room(name, int(cap) if cap is not None else None)
                if cap is not None:
                    capacity_lines.setdefault(name, number)
                names.append(name)
            if len(names) == 2:
                anthill.add_tunnel(*names)
        except ValueError as exc:
            raise AnthillFormatError(str(exc), number, raw.strip()) from None

    if anthill is None:
        raise AnthillFormatError("fichier vide : aucun nombre de fourmis")
    anthill.validate()
    return anthill


def load_anthill(path: str | Path) -> Anthill:
    return parse_anthill_text(Path(path).read_text(encoding="utf-8-sig"))


# ---------------------------------------------------------------------------
# Sorties
# ---------------------------------------------------------------------------


def format_solution(solution: Solution) -> str:
    lines: List[str] = []
    for index, moves in enumerate(solution.steps, start=1):
        lines.append(f"+++ E{index} +++")
        if not moves:
            lines.append("(aucun déplacement)")
        for ant, origin, destination in moves:
            lines.append(f"{ant} - {origin} - {destination}")
    lines.append("")
    lines.append(
        f"Toutes les fourmis atteignent Sd en {solution.turns} étape(s) "
        f"(borne basse BFS d = {solution.lower_bound}) : minimum garanti."
    )
    return "\n".join(lines)


def edge_traffic(solution: Solution) -> Dict[Tuple[str, str], int]:
    """Nombre total de passages par tunnel orienté (origine, destination)."""
    traffic: Counter = Counter()
    for moves in solution.steps:
        for _, origin, dest in moves:
            traffic[(origin, dest)] += 1
    return dict(traffic)


def occupancy_at(solution: Solution, t: int) -> Counter:
    return Counter(path[t] for path in solution.trajectories.values())


def solution_stats(anthill: Anthill, solution: Solution) -> Dict[str, object]:
    """Indicateurs chiffrés d'une résolution (utilisés par main.py et le résumé)."""
    caps = [anthill.room_capacity(r) for r in anthill.intermediate_rooms]
    traffic = edge_traffic(solution)
    used = {frozenset(e) for e in traffic}
    tunnels = anthill.tunnels
    waits = sum(
        1
        for path in solution.trajectories.values()
        for before, after in zip(path, path[1:])
        if before == after and before != SINK
    )
    saturated = {}
    for t in range(solution.turns + 1):
        occ = occupancy_at(solution, t)
        for room in anthill.intermediate_rooms:
            if occ[room] >= anthill.room_capacity(room):
                saturated[room] = saturated.get(room, 0) + 1
    arrivals = solution.arrival_times()
    throughput, bottleneck = anthill.throughput_bottleneck()
    return {
        "fourmis": anthill.ant_count,
        "salles_total": len(anthill.rooms),
        "salles_intermediaires": len(caps),
        "tunnels": len(tunnels),
        "capacite_min": min(caps) if caps else None,
        "capacite_max": max(caps) if caps else None,
        "capacite_moyenne": round(sum(caps) / len(caps), 2) if caps else None,
        "distance_min_d": solution.lower_bound,
        "etapes_optimales_T": solution.turns,
        "mouvements_total": solution.move_count(),
        "attentes": waits,
        "tunnels_utilises": len(used),
        "tunnels_jamais_utilises": len(tunnels) - len(used),
        "tunnel_direct_Sv_Sd": anthill.graph.has_edge(SOURCE, SINK),
        "somme_dates_arrivee": sum(arrivals.values()),
        "debit_max_par_etape": throughput,
        "goulot_coupe_minimale": bottleneck,
        "horizons_testes": [{"T": t, "max_fourmis": f} for t, f in solution.horizon_flows],
        "salles_saturees": dict(sorted(saturated.items(), key=lambda kv: room_sort_key(kv[0]))),
        "trafic_tunnels": {f"{a}->{b}": n for (a, b), n in sorted(traffic.items(), key=lambda kv: (room_sort_key(kv[0][0]), room_sort_key(kv[0][1])))},
    }
