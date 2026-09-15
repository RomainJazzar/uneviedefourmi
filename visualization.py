from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import networkx as nx
from PIL import Image

from ants import Anthill, SINK, SOURCE, Solution, _room_sort_key


def compute_layout(anthill: Anthill) -> Dict[str, tuple[float, float]]:
    """Produit une disposition stable et lisible, du vestibule vers le dortoir."""
    graph = anthill.graph
    distance_from_source = nx.single_source_shortest_path_length(graph, SOURCE)
    max_layer = max(distance_from_source.values()) if distance_from_source else 1
    layers: Dict[int, List[str]] = defaultdict(list)
    for node in graph.nodes:
        layers[distance_from_source.get(node, max_layer + 1)].append(node)

    pos: Dict[str, tuple[float, float]] = {}
    for layer, nodes in sorted(layers.items()):
        nodes = sorted(nodes, key=_room_sort_key)
        n = len(nodes)
        for idx, node in enumerate(nodes):
            y = 0.0 if n == 1 else 1.0 - 2.0 * idx / (n - 1)
            pos[node] = (float(layer), y)

    pos[SOURCE] = (0.0, 0.0)
    pos[SINK] = (float(max_layer), 0.0)
    return pos


def _node_label(anthill: Anthill, node: str) -> str:
    if node == SOURCE:
        return "Sv\nVestibule"
    if node == SINK:
        return "Sd\nDortoir"
    cap = anthill.room_capacity(node)
    return f"{node}\ncap. {cap}" if cap != 1 else node


def draw_graph(anthill: Anthill, output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pos = compute_layout(anthill)
    fig, ax = plt.subplots(figsize=(11, 6.2))
    nx.draw_networkx_edges(anthill.graph, pos, ax=ax, width=2.2, edge_color="#8B6B4E")
    node_colors = [
        "#B7D77A" if n == SOURCE else "#D7C3A5" if n == SINK else "#F1E3C8"
        for n in anthill.graph.nodes
    ]
    nx.draw_networkx_nodes(
        anthill.graph,
        pos,
        ax=ax,
        node_color=node_colors,
        node_size=2100,
        edgecolors="#5A3D2B",
        linewidths=1.8,
    )
    nx.draw_networkx_labels(
        anthill.graph,
        pos,
        labels={n: _node_label(anthill, n) for n in anthill.graph.nodes},
        font_size=10,
        font_weight="bold",
        ax=ax,
    )
    ax.set_title("Fourmilière - représentation sous forme de graphe", fontsize=16, weight="bold")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def draw_step(
    anthill: Anthill,
    solution: Solution,
    time_index: int,
    output_path: str | Path,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pos = compute_layout(anthill)
    occupancy = Counter(path[time_index] for path in solution.trajectories.values())

    fig, ax = plt.subplots(figsize=(11, 6.2))
    nx.draw_networkx_edges(anthill.graph, pos, ax=ax, width=2.2, edge_color="#8B6B4E")
    node_colors = []
    for node in anthill.graph.nodes:
        if node == SOURCE:
            node_colors.append("#B7D77A")
        elif node == SINK:
            node_colors.append("#D7C3A5")
        elif occupancy[node] > 0:
            node_colors.append("#FFCC66")
        else:
            node_colors.append("#F1E3C8")
    nx.draw_networkx_nodes(
        anthill.graph,
        pos,
        ax=ax,
        node_color=node_colors,
        node_size=2300,
        edgecolors="#5A3D2B",
        linewidths=1.8,
    )

    labels = {}
    for node in anthill.graph.nodes:
        base = _node_label(anthill, node)
        if occupancy[node]:
            base += f"\n{occupancy[node]} fourmi(s)"
        labels[node] = base
    nx.draw_networkx_labels(anthill.graph, pos, labels=labels, font_size=9, font_weight="bold", ax=ax)

    title = "État initial" if time_index == 0 else f"Après l'étape E{time_index}"
    ax.set_title(f"{title} - {occupancy[SINK]}/{anthill.ant_count} fourmis au dortoir", fontsize=15, weight="bold")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def export_animation(
    anthill: Anthill,
    solution: Solution,
    output_dir: str | Path,
    gif_name: str = "animation.gif",
) -> List[Path]:
    output_dir = Path(output_dir)
    frames_dir = output_dir / "etapes"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame_paths: List[Path] = []
    for t in range(solution.turns + 1):
        path = frames_dir / f"etape_{t:02d}.png"
        draw_step(anthill, solution, t, path)
        frame_paths.append(path)

    images = [Image.open(p).convert("RGB") for p in frame_paths]
    gif_path = output_dir / gif_name
    images[0].save(
        gif_path,
        save_all=True,
        append_images=images[1:],
        duration=1150,
        loop=0,
        optimize=True,
    )
    for image in images:
        image.close()
    return frame_paths
