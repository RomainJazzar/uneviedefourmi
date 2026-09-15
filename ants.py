from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re
from typing import Dict, Iterable, List, Tuple

import networkx as nx

SOURCE = "Sv"
SINK = "Sd"


@dataclass(frozen=True)
class Room:
    """Une salle de la fourmilière."""

    name: str
    capacity: int = 1

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError(f"La capacité de {self.name} doit être >= 1.")


@dataclass
class Solution:
    """Résultat complet d'une résolution."""

    turns: int
    trajectories: Dict[str, List[str]]
    steps: List[List[Tuple[str, str, str]]]


class Anthill:
    """Modèle d'une fourmilière sous forme de graphe non orienté."""

    def __init__(self, ant_count: int) -> None:
        if ant_count < 1:
            raise ValueError("Le nombre de fourmis doit être un entier >= 1.")
        self.ant_count = ant_count
        self.graph = nx.Graph()
        self.capacities: Dict[str, int] = {SOURCE: ant_count, SINK: ant_count}
        self.graph.add_nodes_from([SOURCE, SINK])

    def add_room(self, room: str, capacity: int | None = None) -> None:
        room = room.strip()
        if not room:
            raise ValueError("Nom de salle vide.")
        if capacity is None:
            capacity = self.capacities.get(room, 1)
        if capacity < 1:
            raise ValueError(f"Capacité invalide pour {room}: {capacity}")
        if room in (SOURCE, SINK):
            # Vestibule et dortoir sont considérés comme non limitants.
            capacity = self.ant_count
        self.capacities[room] = max(capacity, self.capacities.get(room, 0))
        self.graph.add_node(room)

    def add_tunnel(self, room_a: str, room_b: str) -> None:
        if room_a == room_b:
            raise ValueError("Un tunnel ne peut pas relier une salle à elle-même.")
        self.add_room(room_a)
        self.add_room(room_b)
        self.graph.add_edge(room_a, room_b)

    def room_capacity(self, room: str) -> int:
        return self.ant_count if room in (SOURCE, SINK) else self.capacities.get(room, 1)

    def adjacency_matrix(self) -> tuple[list[str], list[list[int]]]:
        nodes = sorted(self.graph.nodes, key=_room_sort_key)
        matrix = nx.to_numpy_array(self.graph, nodelist=nodes, dtype=int)
        return nodes, matrix.astype(int).tolist()

    def validate(self) -> None:
        if SOURCE not in self.graph or SINK not in self.graph:
            raise ValueError("La fourmilière doit contenir Sv et Sd.")
        if not nx.has_path(self.graph, SOURCE, SINK):
            raise ValueError("Aucun chemin ne relie Sv à Sd.")

    def solve(self) -> Solution:
        """
        Trouve un ordonnancement optimal en nombre d'étapes.

        Idée : on transforme le problème en un flot dans le temps.
        Pour un horizon T, chaque salle est copiée pour chaque instant 0..T.
        La capacité d'une salle devient une capacité de noeud (via un découpage
        entrée/sortie). On cherche alors si F unités de flot peuvent aller de Sv
        à Sd. Le premier T faisable est optimal.
        """
        self.validate()
        shortest = nx.shortest_path_length(self.graph, SOURCE, SINK)
        # Une route simple de longueur d permet toujours un pipeline d'au moins
        # une fourmi par étape : d + F - 1 est donc une borne supérieure sûre.
        upper = shortest + self.ant_count - 1

        best_horizon: int | None = None
        for horizon in range(shortest, upper + 1):
            expanded = self._build_time_expanded_graph(horizon, with_costs=False)
            flow_value, _ = nx.maximum_flow(
                expanded,
                "__source__",
                "__sink__",
                capacity="capacity",
                flow_func=nx.algorithms.flow.edmonds_karp,
            )
            if flow_value >= self.ant_count:
                best_horizon = horizon
                break

        if best_horizon is None:
            raise RuntimeError("Aucune solution trouvée malgré l'existence d'un chemin.")

        # À horizon minimal, on calcule ensuite un flot de coût minimal afin de
        # privilégier les arrivées tôt au dortoir et obtenir une solution lisible.
        cost_graph = self._build_time_expanded_graph(best_horizon, with_costs=True)
        flow = nx.min_cost_flow(cost_graph, demand="demand", capacity="capacity", weight="weight")
        trajectories = self._decompose_flow(flow, best_horizon)
        steps = self._trajectories_to_steps(trajectories, best_horizon)
        self._validate_solution(trajectories, best_horizon)
        return Solution(best_horizon, trajectories, steps)

    def _build_time_expanded_graph(self, horizon: int, with_costs: bool) -> nx.DiGraph:
        g = nx.DiGraph()
        f = self.ant_count
        distances = nx.single_source_shortest_path_length(self.graph, SINK)

        g.add_node("__source__", demand=-f if with_costs else 0)
        g.add_node("__sink__", demand=f if with_costs else 0)

        for t in range(horizon + 1):
            for room in self.graph.nodes:
                node_in = (room, t, "in")
                node_out = (room, t, "out")
                g.add_node(node_in, demand=0)
                g.add_node(node_out, demand=0)
                g.add_edge(
                    node_in,
                    node_out,
                    capacity=self.room_capacity(room),
                    weight=0,
                )

        g.add_edge("__source__", (SOURCE, 0, "in"), capacity=f, weight=0)
        g.add_edge((SINK, horizon, "out"), "__sink__", capacity=f, weight=0)

        for t in range(horizon):
            # Attente dans la même salle.
            for room in self.graph.nodes:
                wait_cost = self._transition_cost(room, room, distances) if with_costs else 0
                g.add_edge(
                    (room, t, "out"),
                    (room, t + 1, "in"),
                    capacity=self.room_capacity(room),
                    weight=wait_cost,
                )

            # Déplacement dans un tunnel, dans les deux sens.
            for u, v in self.graph.edges:
                for origin, dest in ((u, v), (v, u)):
                    move_cost = self._transition_cost(origin, dest, distances) if with_costs else 0
                    g.add_edge(
                        (origin, t, "out"),
                        (dest, t + 1, "in"),
                        capacity=f,
                        weight=move_cost,
                    )
        return g

    @staticmethod
    def _transition_cost(origin: str, destination: str, distances: Dict[str, int]) -> int:
        # Une fois au dortoir, rester ne coûte rien : le flot préfère donc les
        # arrivées les plus précoces. Avant Sd, chaque étape coûte 1000, puis une
        # petite pénalité guide les égalités vers les salles proches de Sd.
        if destination == SINK:
            return 0
        distance_penalty = distances.get(destination, 10_000)
        wait_penalty = 2 if origin == destination else 0
        return 1000 + distance_penalty + wait_penalty

    def _decompose_flow(self, flow: Dict, horizon: int) -> Dict[str, List[str]]:
        remaining: Dict[object, Dict[object, int]] = {
            u: {v: int(value) for v, value in nbrs.items()}
            for u, nbrs in flow.items()
        }
        trajectories: Dict[str, List[str]] = {}

        for ant_idx in range(1, self.ant_count + 1):
            node: object = "__source__"
            path: list[object] = [node]
            guard = 0
            while node != "__sink__":
                candidates = [v for v, value in remaining.get(node, {}).items() if value > 0]
                if not candidates:
                    raise RuntimeError("Impossible de décomposer le flot en trajectoires de fourmis.")
                # Ordre déterministe pour rendre les sorties reproductibles.
                candidates.sort(key=str)
                nxt = candidates[0]
                remaining[node][nxt] -= 1
                node = nxt
                path.append(node)
                guard += 1
                if guard > (horizon + 1) * (len(self.graph) * 3 + 2):
                    raise RuntimeError("Cycle inattendu lors de la décomposition du flot.")

            by_time: Dict[int, str] = {}
            for item in path:
                if isinstance(item, tuple) and len(item) == 3:
                    room, t, side = item
                    if side == "in":
                        by_time[int(t)] = str(room)
            trajectory = [by_time[t] for t in range(horizon + 1)]
            trajectories[f"f{ant_idx}"] = trajectory
        return trajectories

    @staticmethod
    def _trajectories_to_steps(
        trajectories: Dict[str, List[str]], horizon: int
    ) -> List[List[Tuple[str, str, str]]]:
        steps: List[List[Tuple[str, str, str]]] = []
        for t in range(1, horizon + 1):
            moves: List[Tuple[str, str, str]] = []
            for ant, path in trajectories.items():
                before, after = path[t - 1], path[t]
                if before != after:
                    moves.append((ant, before, after))
            steps.append(moves)
        return steps

    def _validate_solution(self, trajectories: Dict[str, List[str]], horizon: int) -> None:
        if len(trajectories) != self.ant_count:
            raise AssertionError("Nombre de trajectoires incohérent.")

        for ant, path in trajectories.items():
            if len(path) != horizon + 1 or path[0] != SOURCE or path[-1] != SINK:
                raise AssertionError(f"Trajectoire invalide pour {ant}: {path}")
            for before, after in zip(path, path[1:]):
                if before != after and not self.graph.has_edge(before, after):
                    raise AssertionError(f"Déplacement impossible: {before} -> {after}")

        for t in range(horizon + 1):
            occupancy: Dict[str, int] = {}
            for path in trajectories.values():
                occupancy[path[t]] = occupancy.get(path[t], 0) + 1
            for room, count in occupancy.items():
                if room not in (SOURCE, SINK) and count > self.room_capacity(room):
                    raise AssertionError(
                        f"Capacité dépassée à t={t}: {room} contient {count} fourmis "
                        f"pour une capacité de {self.room_capacity(room)}."
                    )


def parse_room_token(token: str) -> tuple[str, int | None]:
    """Analyse S3 ou S3{4}."""
    token = token.strip()
    match = re.fullmatch(r"([A-Za-zÀ-ÿ0-9_]+)(?:\{(\d+)\})?", token)
    if not match:
        raise ValueError(f"Salle mal formée: {token!r}")
    name = match.group(1)
    capacity = int(match.group(2)) if match.group(2) else None
    return name, capacity


def parse_anthill_text(text: str) -> Anthill:
    """
    Parse un format volontairement tolérant.

    Formats acceptés pour le nombre de fourmis :
      8
      F=8
      fourmis: 8

    Tunnels :
      Sv-S1
      S1{3} - S2

    Capacité seule (optionnel) :
      S4{5}

    Les lignes vides et les commentaires commençant par # sont ignorés.
    """
    raw_lines = [line.split("#", 1)[0].strip() for line in text.splitlines()]
    lines = [line for line in raw_lines if line]
    if not lines:
        raise ValueError("Fichier vide.")

    ant_count: int | None = None
    start_index = 0
    first = lines[0]
    count_match = re.fullmatch(r"(?i)(?:F|fourmis|ants)?\s*[:=]?\s*(\d+)", first)
    if count_match:
        ant_count = int(count_match.group(1))
        start_index = 1
    if ant_count is None:
        raise ValueError(
            "La première ligne doit indiquer le nombre de fourmis (ex. 8, F=8 ou fourmis: 8)."
        )

    anthill = Anthill(ant_count)
    for line in lines[start_index:]:
        # Accepte le tiret normal, un tiret long ou un séparateur avec espaces.
        if "-" in line or "–" in line or "—" in line:
            normalized = line.replace("–", "-").replace("—", "-")
            parts = [p.strip() for p in normalized.split("-") if p.strip()]
            if len(parts) != 2:
                raise ValueError(f"Tunnel mal formé: {line!r}")
            (a, cap_a), (b, cap_b) = parse_room_token(parts[0]), parse_room_token(parts[1])
            anthill.add_room(a, cap_a)
            anthill.add_room(b, cap_b)
            anthill.add_tunnel(a, b)
        else:
            room, capacity = parse_room_token(line)
            anthill.add_room(room, capacity)

    anthill.validate()
    return anthill


def load_anthill(path: str | Path) -> Anthill:
    path = Path(path)
    return parse_anthill_text(path.read_text(encoding="utf-8"))


def format_solution(solution: Solution) -> str:
    lines: List[str] = []
    for index, moves in enumerate(solution.steps, start=1):
        lines.append(f"+++ E{index} +++")
        if not moves:
            lines.append("(aucun déplacement)")
        else:
            for ant, origin, destination in moves:
                lines.append(f"{ant} - {origin} - {destination}")
    lines.append("")
    lines.append(f"Toutes les fourmis atteignent Sd en {solution.turns} étape(s), minimum garanti.")
    return "\n".join(lines)


def _room_sort_key(name: str) -> tuple[int, int | str]:
    if name == SOURCE:
        return (0, 0)
    if name == SINK:
        return (2, 0)
    match = re.fullmatch(r"S(\d+)", name)
    if match:
        return (1, int(match.group(1)))
    return (1, name)
