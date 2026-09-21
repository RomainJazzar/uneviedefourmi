"""Résolution des fourmilières et génération de tous les fichiers de sortie.

    python main.py inputs/officiels/fourmiliere_cinq.txt
    python main.py inputs/officiels            # tout un dossier
    python main.py inputs/officiels --sans-visuels
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import time

from ants import format_solution, load_anthill, solution_stats
from visualization import compute_layout, draw_cumulative_flow, draw_graph, export_animation


def export_adjacency_matrix(anthill, path: Path) -> None:
    nodes, matrix = anthill.adjacency_matrix()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow([""] + nodes)
        for node, row in zip(nodes, matrix):
            writer.writerow([node] + row)


def run(input_path: Path, output_root: Path, visuals: bool = True, quiet: bool = False) -> dict:
    anthill = load_anthill(input_path)
    for warning in anthill.warnings:
        print(f"Attention ({input_path.name}) : {warning}", file=sys.stderr)
    start = time.perf_counter()
    solution = anthill.solve()
    elapsed = time.perf_counter() - start

    case_dir = output_root / input_path.stem
    case_dir.mkdir(parents=True, exist_ok=True)
    result_text = format_solution(solution)
    if not quiet:
        print(result_text)
    (case_dir / "solution.txt").write_text(result_text + "\n", encoding="utf-8")
    export_adjacency_matrix(anthill, case_dir / "matrice_adjacence.csv")

    stats = {"fichier": input_path.name, **solution_stats(anthill, solution), "temps_resolution_s": round(elapsed, 4)}
    (case_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if visuals:
        pos = compute_layout(anthill)  # mêmes positions pour toutes les images
        name = input_path.stem
        draw_graph(anthill, case_dir / "graphe.png", name=name, pos=pos)
        draw_cumulative_flow(anthill, solution, case_dir / "flow_cumule.png", name=name, pos=pos)
        export_animation(anthill, solution, case_dir, name=name, pos=pos)

    print(
        f"-> {input_path.name} : F={anthill.ant_count}, d={solution.lower_bound}, "
        f"T optimal={solution.turns} ({elapsed * 1000:.0f} ms)  ->  {case_dir}"
    )
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Une vie de fourmi - résolution optimale et visualisation.")
    parser.add_argument("input", type=Path, help="Fichier .txt ou dossier contenant plusieurs fourmilières.")
    parser.add_argument("--output", type=Path, default=Path("outputs"), help="Dossier de sortie (défaut : outputs).")
    parser.add_argument("--sans-visuels", action="store_true", help="Ne génère pas les images ni le GIF.")
    parser.add_argument("--quiet", action="store_true", help="N'affiche pas le détail des étapes.")
    return parser


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    files = sorted(args.input.glob("*.txt")) if args.input.is_dir() else [args.input]
    if not files:
        print(f"Erreur : aucun fichier .txt dans {args.input}", file=sys.stderr)
        return 1
    failures = 0
    for input_file in files:
        if len(files) > 1 and not args.quiet:
            print(f"\n{'=' * 72}\nRésolution : {input_file.name}\n{'=' * 72}")
        try:
            run(input_file, args.output, visuals=not args.sans_visuels, quiet=args.quiet)
        except Exception as exc:  # message clair, et code de retour != 0
            failures += 1
            print(f"Erreur sur {input_file.name} : {exc}", file=sys.stderr)
    if failures:
        print(f"{failures} fichier(s) en échec sur {len(files)}.", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
