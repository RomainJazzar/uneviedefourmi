from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

from ants import format_solution, load_anthill
from visualization import draw_graph, export_animation


def export_adjacency_matrix(anthill, path: Path) -> None:
    nodes, matrix = anthill.adjacency_matrix()
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow([""] + nodes)
        for node, row in zip(nodes, matrix):
            writer.writerow([node] + row)


def run(input_path: Path, output_root: Path) -> int:
    anthill = load_anthill(input_path)
    solution = anthill.solve()

    case_dir = output_root / input_path.stem
    case_dir.mkdir(parents=True, exist_ok=True)

    result_text = format_solution(solution)
    print(result_text)
    (case_dir / "solution.txt").write_text(result_text + "\n", encoding="utf-8")
    draw_graph(anthill, case_dir / "graphe.png")
    export_animation(anthill, solution, case_dir)
    export_adjacency_matrix(anthill, case_dir / "matrice_adjacence.csv")

    print(f"\nFichiers générés dans : {case_dir.resolve()}")
    print("- graphe.png")
    print("- solution.txt")
    print("- matrice_adjacence.csv")
    print("- animation.gif")
    print("- etapes/etape_XX.png")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Une vie de fourmi - résolution optimale et visualisation."
    )
    parser.add_argument("input", type=Path, help="Fichier .txt ou dossier contenant plusieurs fourmilières.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs"),
        help="Dossier de sortie (défaut: outputs).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.input.is_dir():
            files = sorted(args.input.glob("*.txt"))
            if not files:
                raise ValueError(f"Aucun fichier .txt trouvé dans {args.input}.")
            failures = 0
            for input_file in files:
                print(f"\n{'=' * 72}\nRésolution : {input_file.name}\n{'=' * 72}")
                try:
                    run(input_file, args.output)
                except Exception as exc:
                    failures += 1
                    print(f"Erreur sur {input_file.name} : {exc}", file=sys.stderr)
            return 1 if failures else 0
        return run(args.input, args.output)
    except Exception as exc:  # message propre pour une soutenance/démo
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
