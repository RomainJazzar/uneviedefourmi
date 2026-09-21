"""Analyse automatique de toutes les fourmilières officielles.

    python tools/analyze_inputs.py [dossier_inputs] [dossier_sortie]

Produit outputs/summary/results.csv, results.json, results.md et resultats.png.
Code de retour 1 si une seule fourmilière ne peut pas être résolue.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker

from ants import load_anthill, solution_stats

COLUMNS = [
    ("fichier", "fichier"),
    ("fourmis", "F"),
    ("salles_total", "salles"),
    ("salles_intermediaires", "salles interm."),
    ("tunnels", "tunnels"),
    ("capacite_min", "cap. min"),
    ("capacite_max", "cap. max"),
    ("capacite_moyenne", "cap. moy."),
    ("distance_min_d", "d (BFS)"),
    ("etapes_optimales_T", "T optimal"),
    ("mouvements_total", "mouvements"),
    ("attentes", "attentes"),
    ("tunnels_utilises", "tunnels utilisés"),
    ("tunnels_jamais_utilises", "tunnels inutilisés"),
    ("debit_max_par_etape", "débit max/étape"),
    ("temps_ms", "temps (ms)"),
]


OFFICIAL_ORDER = ["zero", "un", "deux", "trois", "quatre", "cinq", "3D", "La_hormiguera", "salle"]


def _order(path: Path) -> tuple:
    rank = next((i for i, key in enumerate(OFFICIAL_ORDER) if key in path.stem), len(OFFICIAL_ORDER))
    return (rank, path.name.lower())


def analyze(input_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(input_dir.glob("*.txt"), key=_order):
        anthill = load_anthill(path)
        timings = []
        for _ in range(3):  # meilleur de 3 exécutions, pour un chiffre stable
            start = time.perf_counter()
            solution = anthill.solve()
            timings.append(time.perf_counter() - start)
        stats = solution_stats(anthill, solution)
        rows.append({"fichier": path.name, **stats, "temps_ms": round(min(timings) * 1000, 1)})
    return rows


def write_tables(rows: list[dict], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (out / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow([key for key, _ in COLUMNS])
        for row in rows:
            writer.writerow(["" if row[key] is None else row[key] for key, _ in COLUMNS])

    def cell(value):
        return "illimité" if value is None else str(value)

    lines = [
        "# Résultats sur les fourmilières officielles",
        "",
        f"**{len(rows)} / {len(rows)} fichiers résolus**, toutes les solutions vérifiées "
        "(capacités, tunnels existants, simultanéité, arrivée de toutes les fourmis).",
        "",
        "| " + " | ".join(label for _, label in COLUMNS) + " |",
        "|" + "|".join("---" if key == "fichier" else "---:" for key, _ in COLUMNS) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(cell(row[key]) for key, _ in COLUMNS) + " |")
    lines += [
        "",
        "- **d** : plus court chemin Sv → Sd (BFS), borne basse : aucune fourmi n'arrive avant.",
        "- **T optimal** : premier horizon pour lequel le max-flow du graphe temporel vaut F.",
        "- **attentes** : nombre de fois où une fourmi pas encore arrivée reste sur place pendant une étape.",
        "- **débit max/étape** : coupe minimale du graphe des salles (fourmis pouvant arriver par étape en régime établi).",
        "- **temps** : résolution complète (recherche de T + min-cost + décomposition), meilleur de 3 exécutions.",
    ]
    (out / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def draw_chart(rows: list[dict], path: Path) -> None:
    """T optimal (barre) comparé à la borne BFS d (trait), une ligne par fichier."""
    ink, muted, grid = "#0b1f2a", "#6b6a66", "#e6e4de"
    blue, bound = "#2a78d6", "#0b1f2a"
    rows = list(reversed(rows))  # barh part du bas : on inverse pour lire dans l'ordre officiel
    fig, ax = plt.subplots(figsize=(13.333, 7.5))
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ys = range(len(rows))
    ax.barh(list(ys), [r["etapes_optimales_T"] for r in rows], height=0.56, color=blue, zorder=2, label="T optimal (nombre d'étapes)")
    for y, r in zip(ys, rows):
        d, t = r["distance_min_d"], r["etapes_optimales_T"]
        ax.plot([d, d], [y - 0.36, y + 0.36], color=bound, lw=3, solid_capstyle="round", zorder=3)
        ax.text(t + 0.25, y, f"T = {t}", va="center", ha="left", fontsize=14, fontweight="bold", color=ink)
        ax.text(t + 2.3, y, f"(d = {d})", va="center", ha="left", fontsize=12, color=muted)
    ax.plot([], [], color=bound, lw=3, label="borne basse d (plus court chemin, BFS)")
    labels = [f"{r['fichier'].removesuffix('.txt')}   F = {r['fourmis']}" for r in rows]
    ax.set_yticks(list(ys), labels, fontsize=13, color=ink)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", colors=muted, labelsize=11)
    ax.set_xlim(0, max(r["etapes_optimales_T"] for r in rows) + 5)
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
    ax.set_xlabel("étapes", color=muted, fontsize=12)
    ax.grid(axis="x", color=grid, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(grid)
    fig.text(0.03, 0.955, f"{len(rows)} / {len(rows)} fourmilières officielles résolues au minimum d'étapes",
             fontsize=20, fontweight="bold", color=ink, va="top")
    fig.text(0.03, 0.9, "L'écart entre d et T, c'est le coût du trafic : capacités limitées et fourmis qui attendent leur tour.",
             fontsize=13, color=muted, va="top")
    fig.legend(loc="upper left", bbox_to_anchor=(0.3, 0.86), ncol=2, frameon=False, fontsize=12.5)
    fig.subplots_adjust(left=0.3, right=0.97, top=0.8, bottom=0.1)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor(), metadata={"Software": None})
    plt.close(fig)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    input_dir = Path(argv[0]) if argv else ROOT / "inputs" / "officiels"
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "outputs" / "summary"
    try:
        rows = analyze(input_dir)
    except Exception as exc:
        print(f"Échec de l'analyse : {exc}", file=sys.stderr)
        return 1
    if not rows:
        print(f"Aucune fourmilière dans {input_dir}", file=sys.stderr)
        return 1
    write_tables(rows, out)
    draw_chart(rows, out / "resultats.png")
    for row in rows:
        print(f"{row['fichier']:34s} F={row['fourmis']:>3}  d={row['distance_min_d']:>2}  T={row['etapes_optimales_T']:>2}  {row['temps_ms']:>7.1f} ms")
    print(f"{len(rows)} fichiers analysés -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
