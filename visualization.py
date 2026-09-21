"""Visualisations : graphe, étapes, GIF et trafic cumulé.

Toutes les images d'une même fourmilière utilisent exactement les mêmes
positions (compute_layout est déterministe) : le graphe ne « saute » pas
d'une frame à l'autre et les slides reprennent les mêmes dessins.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import math
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch
from PIL import Image

from ants import SINK, SOURCE, Anthill, Solution, bfs_distances, edge_traffic, occupancy_at, room_sort_key

Pos = Dict[str, Tuple[float, float]]

# Palette (validée daltonisme : bleu / orange ; gris neutre ; rouge réservé aux goulots)
INK = "#0b1f2a"
MUTED = "#6b6a66"
UNUSED = "#cfcdc6"
CUMUL = "#2a78d6"
CUMUL_LIGHT = "#9ec5f4"
MOVE = "#eb6834"
FULL = "#e34948"
ROOM_FILL = "#ffffff"
SEQ = ["#ffffff", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf"]
BACKGROUND = "#fcfcfb"

FIGSIZE = (13.333, 7.5)  # 16:9, identique aux slides

plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def _crossings(upper: List[str], lower: List[str], edges: set) -> int:
    pos_u = {n: i for i, n in enumerate(upper)}
    pos_l = {n: i for i, n in enumerate(lower)}
    pairs = [(pos_u[a], pos_l[b]) for a in upper for b in lower if frozenset((a, b)) in edges]
    return sum(1 for i, (a1, b1) in enumerate(pairs) for a2, b2 in pairs[i + 1:] if (a1 - a2) * (b1 - b2) < 0)


def compute_layout(anthill: Anthill) -> Pos:
    """Disposition en couches, de gauche (Sv) à droite (Sd).

    - colonne = distance BFS depuis Sv (Sd toujours dans la dernière colonne) ;
    - ordre dans chaque colonne = heuristique du barycentre (réduit les croisements) ;
    - une colonne reliée à elle-même est posée sur un arc pour que ses tunnels internes
      ne se superposent pas.
    Aucune part d'aléatoire : même entrée -> mêmes positions.
    """
    graph = anthill.graph
    dist = bfs_distances(graph, SOURCE)
    rooms = anthill.rooms
    last = max([d for r, d in dist.items() if r != SINK] + [0]) + 1
    layer_of: Dict[str, int] = {}
    for room in rooms:
        if room == SINK:
            layer_of[room] = last
        elif room in dist:
            layer_of[room] = dist[room]
    orphans = [r for r in rooms if r not in layer_of]

    layers: Dict[int, List[str]] = defaultdict(list)
    for room in rooms:
        if room in layer_of:
            layers[layer_of[room]].append(room)
    order = [layers[k] for k in range(last + 1)]
    edges = {frozenset(e) for e in graph.edges}

    def total_crossings(o):
        return sum(_crossings(o[k], o[k + 1], edges) for k in range(len(o) - 1))

    def barycenter(room, reference):
        idx = {n: i - (len(reference) - 1) / 2 for i, n in enumerate(reference)}
        values = [idx[n] for n in graph.neighbors(room) if n in idx]
        return sum(values) / len(values) if values else None

    best, best_score = [list(l) for l in order], total_crossings(order)
    for sweep in range(8):
        rng = range(1, len(order)) if sweep % 2 == 0 else range(len(order) - 2, -1, -1)
        for k in rng:
            ref = order[k - 1] if sweep % 2 == 0 else order[k + 1]
            current = {n: i - (len(order[k]) - 1) / 2 for i, n in enumerate(order[k])}
            order[k] = sorted(
                order[k],
                key=lambda n: (barycenter(n, ref) if barycenter(n, ref) is not None else current[n], room_sort_key(n)),
            )
        score = total_crossings(order)
        if score < best_score:
            best, best_score = [list(l) for l in order], score
    order = best

    tallest = max(len(l) for l in order)
    x_step = max(1.0, tallest * 0.45)
    pos: Pos = {}
    x = 0.0
    for k, layer in enumerate(order):
        n = len(layer)
        internal = sum(1 for i, a in enumerate(layer) for b in layer[i + 1:] if frozenset((a, b)) in edges)
        if internal >= n >= 4:
            # colonne très reliée à elle-même (ex. clique) : salles posées sur une ellipse
            half_w, half_h = 0.8 * x_step, max(1.0, (tallest - 1) / 2)
            x += half_w
            for i, room in enumerate(layer):
                theta = math.pi / 2 - 2 * math.pi * (i + 0.5) / n
                pos[room] = (x + half_w * math.cos(theta), half_h * math.sin(theta))
            x += half_w + x_step
            continue
        for i, room in enumerate(layer):
            # petit zigzag si des tunnels relient des salles de la même colonne
            shift = (0.18 * x_step if i % 2 else -0.18 * x_step) if internal else 0.0
            pos[room] = (x + shift, (n - 1) / 2 - i)
        x += x_step
    for i, room in enumerate(orphans):
        pos[room] = ((len(order) / 2 + i) * x_step, -(tallest + 1) / 2)
    return pos


# ---------------------------------------------------------------------------
# Primitives de dessin
# ---------------------------------------------------------------------------


def _node_size(ax, pos: Pos) -> float:
    """Taille des cercles (points²) : le plus grand possible sans chevauchement."""
    pts = {r: ax.transData.transform(p) for r, p in pos.items()}
    names = list(pts)
    closest = min(
        (math.dist(pts[a], pts[b]) for i, a in enumerate(names) for b in names[i + 1:]),
        default=200.0,
    )
    diameter_px = min(0.8 * closest, 0.62 * ax.figure.dpi)
    diameter_pt = diameter_px * 72 / ax.figure.dpi
    return max(diameter_pt, 30) ** 2


def _radius_points(size: float) -> float:
    return math.sqrt(size) / 2


def _edge_curvature(a: str, b: str, pos: Pos) -> float:
    """Courbe un tunnel s'il passerait en ligne droite sur une autre salle."""
    (x1, y1), (x2, y2) = pos[a], pos[b]
    length = math.hypot(x2 - x1, y2 - y1) or 1.0
    for room, (x, y) in pos.items():
        if room in (a, b):
            continue
        t = ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / (length ** 2)
        if 0 < t < 1:
            d = abs((x2 - x1) * (y1 - y) - (x1 - x) * (y2 - y1)) / length
            if d < 0.28:
                return 0.28 if room_sort_key(a) < room_sort_key(b) else -0.28
    return 0.0


def _setup_axes(pos: Pos, headless: bool = False):
    fig, ax = plt.subplots(figsize=FIGSIZE)
    fig.patch.set_facecolor(BACKGROUND)
    ax.set_facecolor(BACKGROUND)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    span_x = max(xs) - min(xs) or 1
    span_y = max(ys) - min(ys) or 1
    mid_y = (max(ys) + min(ys)) / 2
    half_y = max(span_y / 2 + 0.6, 1.5)
    ax.set_xlim(min(xs) - 0.05 * span_x - 0.55, max(xs) + 0.05 * span_x + 0.55)
    ax.set_ylim(mid_y - half_y, mid_y + half_y)
    ax.axis("off")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.97 if headless else 0.86, bottom=0.08)
    return fig, ax


def _draw_edge(ax, pos, a, b, size, color, width, rad=0.0, arrow=False, alpha=1.0, z=1, style="-"):
    shrink = _radius_points(size) + (2 if arrow else 0)
    patch = FancyArrowPatch(
        pos[a],
        pos[b],
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle=f"-|>,head_length={7 + width * 0.9:.1f},head_width={4 + width * 0.8:.1f}" if arrow else "-",
        mutation_scale=1,
        color=color,
        linewidth=width,
        linestyle=style,
        shrinkA=shrink,
        shrinkB=shrink,
        alpha=alpha,
        zorder=z,
        capstyle="round",
    )
    ax.add_patch(patch)
    return patch


def _edge_label_point(ax, pos, a, b, rad, t=0.58):
    """Point de la courbe arc3 (Bézier quadratique, calculée en pixels comme matplotlib),
    un peu après le milieu pour séparer les étiquettes des tunnels qui partent d'une même salle."""
    (x1, y1), (x2, y2) = ax.transData.transform(pos[a]), ax.transData.transform(pos[b])
    cx, cy = (x1 + x2) / 2 + rad * (y2 - y1), (y1 + y2) / 2 - rad * (x2 - x1)
    u = 1 - t
    point = (u * u * x1 + 2 * u * t * cx + t * t * x2, u * u * y1 + 2 * u * t * cy + t * t * y2)
    return ax.transData.inverted().transform(point)


def _label_box(ax, x, y, text, color, size=11, z=6):
    ax.text(
        x, y, text, ha="center", va="center", fontsize=size, fontweight="bold", color=color, zorder=z,
        bbox=dict(boxstyle="round,pad=0.18", fc="white", ec=color, lw=1.2),
    )


def _draw_nodes(ax, anthill, pos, size, fills, labels, rings=None, text_colors=None):
    rings = rings or {}
    text_colors = text_colors or {}
    for room in anthill.rooms:
        x, y = pos[room]
        special = room in (SOURCE, SINK)
        s = size * (1.35 if special else 1.0)
        ax.scatter([x], [y], s=s, c=[fills[room]], edgecolors=rings.get(room, INK), linewidths=3.2 if room in rings else 1.6, zorder=4)
        name, detail = labels[room]
        color = text_colors.get(room, "white" if special else INK)
        diameter = math.sqrt(size)
        big = diameter >= 44
        common = dict(ha="center", va="center", color=color, zorder=5, textcoords="offset points")
        ax.annotate(name, (x, y), xytext=(0, 6 if detail else 0), fontsize=(13 if big else 11) + (1 if special else 0), fontweight="bold", **common)
        if detail:
            ax.annotate(detail, (x, y), xytext=(0, -8), fontsize=10 if big else 8.5, **common)


def _legend(ax, handles, ncol=None):
    leg = ax.legend(
        handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.06), ncol=ncol or len(handles),
        frameon=False, fontsize=11, handlelength=2.4, columnspacing=1.6,
    )
    for text in leg.get_texts():
        text.set_color(INK)


def _title(fig, title, subtitle=None):
    if getattr(fig, "_headless", False):
        return  # version pour les slides : le titre est porté par la slide
    fig.text(0.03, 0.955, title, fontsize=20, fontweight="bold", color=INK, ha="left", va="top")
    if subtitle:
        fig.text(0.03, 0.905, subtitle, fontsize=12.5, color=MUTED, ha="left", va="top")


def _save(fig, path, dpi):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, facecolor=fig.get_facecolor(), metadata={"Software": None})
    plt.close(fig)


# ---------------------------------------------------------------------------
# Graphe statique
# ---------------------------------------------------------------------------


def draw_graph(anthill: Anthill, output_path, name: str = "", pos: Pos | None = None, dpi: int = 150, headless: bool = False) -> None:
    pos = pos or compute_layout(anthill)
    fig, ax = _setup_axes(pos, headless)
    fig._headless = headless
    size = _node_size(ax, pos)
    for a, b in anthill.tunnels:
        _draw_edge(ax, pos, a, b, size, "#8a8983", 2.2, rad=_edge_curvature(a, b, pos))
    fills, labels = {}, {}
    for room in anthill.rooms:
        if room in (SOURCE, SINK):
            fills[room] = INK
            labels[room] = (room, "vestibule" if room == SOURCE else "dortoir")
        else:
            cap = anthill.room_capacity(room)
            fills[room] = SEQ[min(len(SEQ) - 1, 1 + (cap > 1) + (cap > 3) + (cap > 10))] if cap > 1 else ROOM_FILL
            labels[room] = (room, f"cap {cap}")
    _draw_nodes(ax, anthill, pos, size, fills, labels)
    caps = [anthill.room_capacity(r) for r in anthill.intermediate_rooms]
    cap_text = f"capacités {min(caps)} à {max(caps)}" if caps and min(caps) != max(caps) else f"capacité {caps[0] if caps else '-'}"
    _title(
        fig,
        f"{name or 'Fourmilière'} : {anthill.ant_count} fourmis",
        f"{len(anthill.intermediate_rooms)} salles intermédiaires · {len(anthill.tunnels)} tunnels · {cap_text}"
        + (" · tunnel direct Sv–Sd" if anthill.graph.has_edge(SOURCE, SINK) else ""),
    )
    _legend(
        ax,
        [
            Line2D([], [], marker="o", ls="", ms=14, mfc=INK, mec=INK, label="Sv / Sd (non limités)"),
            Line2D([], [], marker="o", ls="", ms=14, mfc=ROOM_FILL, mec=INK, label="salle : nom + capacité"),
            Line2D([], [], color="#8a8983", lw=2.2, label="tunnel (sans limite)"),
        ],
    )
    _save(fig, output_path, dpi)


# ---------------------------------------------------------------------------
# Étapes
# ---------------------------------------------------------------------------


def _traffic_until(solution: Solution, t: int) -> Counter:
    traffic: Counter = Counter()
    for moves in solution.steps[:t]:
        for _, a, b in moves:
            traffic[frozenset((a, b))] += 1
    return traffic


def _occupancy_fill(count: int, cap: int) -> str:
    if count == 0:
        return ROOM_FILL
    if count >= cap:
        return SEQ[-1]
    return SEQ[1 + int(3 * count / cap)]  # 1..3 selon le remplissage


def draw_step(anthill: Anthill, solution: Solution, t: int, output_path, name: str = "", pos: Pos | None = None, dpi: int = 110, headless: bool = False) -> None:
    """Frame t : état APRÈS l'étape t (t = 0 : état initial) + mouvements de l'étape t."""
    pos = pos or compute_layout(anthill)
    fig, ax = _setup_axes(pos, headless)
    fig._headless = headless
    size = _node_size(ax, pos)
    f = anthill.ant_count
    occ = occupancy_at(solution, t)
    before = _traffic_until(solution, t - 1) if t > 0 else Counter()
    max_cumul = max(_traffic_until(solution, solution.turns).values() or [1])

    current: Counter = Counter()
    if t > 0:
        for _, a, b in solution.steps[t - 1]:
            current[(a, b)] += 1

    for a, b in anthill.tunnels:
        rad = _edge_curvature(a, b, pos)
        used = before[frozenset((a, b))]
        if used:
            _draw_edge(ax, pos, a, b, size, CUMUL_LIGHT, 1.5 + 7 * used / max_cumul, rad=rad, z=1)
        else:
            _draw_edge(ax, pos, a, b, size, UNUSED, 1.3, rad=rad, z=1)

    for (a, b), n in sorted(current.items(), key=lambda kv: (room_sort_key(kv[0][0]), room_sort_key(kv[0][1]))):
        rad = _edge_curvature(a, b, pos)
        both = (b, a) in current
        if both:
            rad += 0.18
        width = 2.5 + 5.5 * n / max(f, 1) ** 0.5 if f > 1 else 3
        _draw_edge(ax, pos, a, b, size, MOVE, min(width, 9), rad=rad, arrow=True, z=3)
        lx, ly = _edge_label_point(ax, pos, a, b, rad)
        _label_box(ax, lx, ly, f"{n}", MOVE, size=11)

    fills, labels, rings, text_colors = {}, {}, {}, {}
    for room in anthill.rooms:
        count = occ[room]
        if room == SOURCE:
            fills[room] = INK
            labels[room] = ("Sv", f"reste {count}")
        elif room == SINK:
            fills[room] = INK
            labels[room] = ("Sd", f"{count} / {f}")
        else:
            cap = anthill.room_capacity(room)
            fills[room] = _occupancy_fill(count, cap)
            labels[room] = (room, f"{count} / {cap}")
            if count >= cap:
                rings[room] = FULL
            if fills[room] in SEQ[4:]:
                text_colors[room] = "white"
    _draw_nodes(ax, anthill, pos, size, fills, labels, rings, text_colors)

    moving = sum(current.values())
    title = "État initial" if t == 0 else f"Étape E{t} / {solution.turns}"
    _title(
        fig,
        f"{title}   ·   Arrivées : {occ[SINK]} / {f}",
        f"{name}   ·   {moving} fourmi(s) en mouvement pendant cette étape" if t else f"{name}   ·   toutes les fourmis sont dans le vestibule Sv",
    )
    _legend(
        ax,
        [
            Line2D([], [], color=MOVE, lw=4, marker=">", ms=9, label="déplacement de l'étape (n = nb de fourmis)"),
            Line2D([], [], color=CUMUL_LIGHT, lw=5, label="tunnel déjà emprunté"),
            Line2D([], [], color=UNUSED, lw=1.5, label="tunnel pas encore utilisé"),
            Line2D([], [], marker="o", ls="", ms=14, mfc=SEQ[2], mec=INK, label="occupation / capacité"),
            Line2D([], [], marker="o", ls="", ms=14, mfc=SEQ[5], mec=FULL, mew=2.5, label="salle pleine"),
        ],
    )
    _save(fig, output_path, dpi)


def export_animation(anthill: Anthill, solution: Solution, output_dir, name: str = "", gif_name: str = "animation.gif", pos: Pos | None = None) -> List[Path]:
    output_dir = Path(output_dir)
    frames_dir = output_dir / "etapes"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("etape_*.png"):
        old.unlink()
    pos = pos or compute_layout(anthill)
    frame_paths: List[Path] = []
    for t in range(solution.turns + 1):
        path = frames_dir / f"etape_{t:02d}.png"
        draw_step(anthill, solution, t, path, name=name, pos=pos)
        frame_paths.append(path)

    images = [Image.open(p).convert("RGB") for p in frame_paths]
    palette_images = [im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for im in images]
    durations = [1600] + [1300] * (len(images) - 2) + [3500] if len(images) > 1 else [3000]
    palette_images[0].save(
        output_dir / gif_name, save_all=True, append_images=palette_images[1:], duration=durations, loop=0, optimize=True, disposal=1,
    )
    for im in images:
        im.close()
    return frame_paths


# ---------------------------------------------------------------------------
# Trafic cumulé
# ---------------------------------------------------------------------------


def draw_cumulative_flow(anthill: Anthill, solution: Solution, output_path, name: str = "", pos: Pos | None = None, dpi: int = 150, headless: bool = False) -> None:
    """Graphe complet ; épaisseur de chaque tunnel = nombre total de passages."""
    pos = pos or compute_layout(anthill)
    fig, ax = _setup_axes(pos, headless)
    fig._headless = headless
    size = _node_size(ax, pos)
    traffic = edge_traffic(solution)
    peak = max(traffic.values() or [1])

    for a, b in anthill.tunnels:
        rad = _edge_curvature(a, b, pos)
        directions = [(u, v) for u, v in ((a, b), (b, a)) if traffic.get((u, v))]
        if not directions:
            _draw_edge(ax, pos, a, b, size, UNUSED, 1.3, rad=rad, style=(0, (4, 3)))
            continue
        for u, v in directions:
            n = traffic[(u, v)]
            # deux sens utilisés : deux arcs séparés (arc3 courbe du même côté de chaque flèche)
            r = rad + (0.2 if len(directions) == 2 else 0)
            width = 1.8 + 12 * n / peak
            _draw_edge(ax, pos, u, v, size, CUMUL, width, rad=r, arrow=True, z=2)
            lx, ly = _edge_label_point(ax, pos, u, v, r)
            _label_box(ax, lx, ly, str(n), CUMUL, size=11)

    passages = Counter()
    for (u, v), n in traffic.items():
        passages[v] += n
    throughput, bottleneck = anthill.throughput_bottleneck()

    fills, labels, rings = {}, {}, {}
    for room in anthill.rooms:
        if room in (SOURCE, SINK):
            fills[room] = INK
            labels[room] = (room, str(anthill.ant_count))
            continue
        cap = anthill.room_capacity(room)
        fills[room] = ROOM_FILL if passages[room] == 0 else SEQ[2]
        labels[room] = (room, f"cap {cap}")
        if room in bottleneck:
            rings[room] = FULL
    _draw_nodes(ax, anthill, pos, size, fills, labels, rings)

    unused = sum(1 for a, b in anthill.tunnels if not traffic.get((a, b)) and not traffic.get((b, a)))
    if throughput is None:
        neck = "tunnel direct Sv–Sd : aucun goulot"
    else:
        neck = f"goulot {' + '.join(bottleneck)} : au plus {throughput} arrivée(s) par étape"
    _title(
        fig,
        f"Trafic cumulé : {anthill.ant_count} fourmis en {solution.turns} étapes",
        f"{name}   ·   {len(anthill.tunnels) - unused} tunnels utilisés sur {len(anthill.tunnels)}   ·   {neck}",
    )
    _legend(
        ax,
        [
            Line2D([], [], color=CUMUL, lw=7, label="passages (épaisseur ∝ nombre, flèche = sens)"),
            Line2D([], [], color=UNUSED, lw=1.5, ls="--", label="tunnel jamais utilisé"),
            Line2D([], [], marker="o", ls="", ms=14, mfc=SEQ[2], mec=FULL, mew=2.5, label="goulot (coupe minimale)"),
        ],
    )
    _save(fig, output_path, dpi)


# ---------------------------------------------------------------------------
# Graphe temporel (illustration pédagogique)
# ---------------------------------------------------------------------------


def draw_time_expanded(anthill: Anthill, solution: Solution, output_path, dpi: int = 170, figsize=(8.0, 4.6)) -> None:
    """Le graphe « déplié dans le temps » au T optimal, avec les trajets choisis.

    Une colonne par instant t, une ligne par salle. Flèche horizontale = attendre,
    flèche en biais = traverser un tunnel. En orange : les trajets des fourmis
    (le nombre = fourmis sur l'arc). Construit à partir du vrai graphe et de la
    vraie solution.
    """
    rooms = [r for r in anthill.rooms if r in bfs_distances(anthill.graph, SOURCE)]
    horizon = solution.turns
    row = {room: -i for i, room in enumerate(rooms)}
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(BACKGROUND)
    ax.set_facecolor(BACKGROUND)
    ax.axis("off")
    ax.set_xlim(-0.45, horizon + 0.45)
    ax.set_ylim(-len(rooms) + 0.45, 0.85)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)

    used: Counter = Counter()
    for path in solution.trajectories.values():
        for t in range(horizon):
            if path[t] != SINK or path[t + 1] != SINK:
                used[(path[t], t, path[t + 1])] += 1

    size = 900
    shrink = _radius_points(size)

    def arc(a, t, b, color, width, z):
        ax.add_patch(FancyArrowPatch(
            (t, row[a]), (t + 1, row[b]), arrowstyle=f"-|>,head_length={5 + width:.1f},head_width={3 + width * 0.7:.1f}",
            mutation_scale=1, color=color, lw=width, shrinkA=shrink, shrinkB=shrink, zorder=z,
        ))

    for t in range(horizon):
        for room in rooms:
            arc(room, t, room, UNUSED, 1.0, 1)
            for other in anthill.graph.neighbors(room):
                if other in row and room != SINK:
                    arc(room, t, other, UNUSED, 1.0, 1)
    for (a, t, b), n in used.items():
        arc(a, t, b, MOVE, 1.8 + 1.4 * n, 3)
        if n > 1:
            ax.annotate(str(n), ((2 * t + 1) / 2, (row[a] + row[b]) / 2), xytext=(0, 7), textcoords="offset points",
                        ha="center", fontsize=11, fontweight="bold", color=MOVE, zorder=6)

    for t in range(horizon + 1):
        ax.text(t, 0.62, f"t = {t}", ha="center", va="center", fontsize=13, fontweight="bold", color=INK)
        for room in rooms:
            special = room in (SOURCE, SINK)
            ax.scatter([t], [row[room]], s=size, c=[INK if special else ROOM_FILL], edgecolors=INK, linewidths=1.4, zorder=4)
            ax.text(t, row[room], room, ha="center", va="center", fontsize=10.5, fontweight="bold",
                    color="white" if special else INK, zorder=5)
    fig.savefig(Path(output_path), dpi=dpi, facecolor=fig.get_facecolor(), metadata={"Software": None})
    plt.close(fig)
