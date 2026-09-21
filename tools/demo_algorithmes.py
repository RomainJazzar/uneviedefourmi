"""Démonstration : pourquoi un plus court chemin seul ne suffit pas.

    python tools/demo_algorithmes.py

Contre-exemple inputs/demo/plus_court_chemin_vs_trafic.txt (3 fourmis) :
- à gauche, toutes les fourmis n'ont le droit qu'au plus court chemin trouvé par BFS ;
- à droite, notre solveur utilise tout le réseau.

Aucun nouvel algorithme : la stratégie « plus court chemin uniquement » est
obtenue avec le MÊME solveur, appliqué à une fourmilière réduite aux seuls
tunnels de ce chemin. Seul le réseau disponible change.
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import networkx as nx

from ants import SINK, SOURCE, Anthill, format_solution, load_anthill
from visualization import draw_solution_comparison

DEMO_INPUT = ROOT / "inputs" / "demo" / "plus_court_chemin_vs_trafic.txt"
OUT_DIR = ROOT / "outputs" / "demo_algorithmes"


def shortest_path_only(anthill: Anthill) -> Anthill:
    """Même fourmilière, mais réduite aux tunnels d'UN plus court chemin Sv -> Sd."""
    path = nx.shortest_path(anthill.graph, SOURCE, SINK)  # BFS (graphe non pondéré)
    restricted = Anthill(anthill.ant_count)
    for room in anthill.rooms:
        capacity = anthill.explicit_capacities.get(room)
        restricted.add_room(room, capacity)
    for a, b in zip(path, path[1:]):
        restricted.add_tunnel(a, b)
    return restricted


def run(input_path: Path = DEMO_INPUT, out_dir: Path = OUT_DIR) -> dict:
    anthill = load_anthill(input_path)
    naive_anthill = shortest_path_only(anthill)
    path = nx.shortest_path(anthill.graph, SOURCE, SINK)
    naive = naive_anthill.solve()
    best = anthill.solve()
    out_dir.mkdir(parents=True, exist_ok=True)
    warning = (
        "# Contre-exemple pédagogique : stratégie « plus court chemin uniquement »\n"
        f"# (fourmis limitées au chemin {' -> '.join(path)}). Ce n'est PAS la solution du problème.\n"
    )
    (out_dir / "plus_court_chemin_uniquement.txt").write_text(warning + format_solution(naive) + "\n", encoding="utf-8")
    (out_dir / "optimisation_du_trafic.txt").write_text(format_solution(best) + "\n", encoding="utf-8")
    draw_solution_comparison(
        anthill,
        naive,
        best,
        out_dir / "shortest_path_vs_flow.png",
        "Plus court chemin uniquement",
        "Optimisation du trafic (max-flow)",
        ("Le plus court chemin optimise une fourmi.", "Le max-flow optimise toute la colonie."),
        subtitles=(
            f"les {anthill.ant_count} fourmis suivent " + " → ".join(path) + f" (longueur {len(path) - 1}), en file indienne",
            "plusieurs chemins en parallèle, capacités respectées",
        ),
    )
    return {"d": best.lower_bound, "plus_court_chemin": naive.turns, "max_flow": best.turns}


def main() -> int:
    result = run()
    print(
        f"d (BFS) = {result['d']} ; plus court chemin uniquement : {result['plus_court_chemin']} étapes ; "
        f"optimisation du trafic : {result['max_flow']} étapes -> {OUT_DIR}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
