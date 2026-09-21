"""Régénère TOUS les livrables, dans l'ordre, et s'arrête à la première erreur.

    python tools/build_all.py

1. résolution + visualisations des fourmilières officielles et des exemples
2. statistiques de synthèse (outputs/summary) et démonstration plus court chemin / max-flow
3. script oral et fiche de révision (PDF + DOCX)
4. présentation PowerPoint
5. archive ZIP complète
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

STEPS = [
    ["main.py", "inputs/officiels", "--quiet"],
    ["main.py", "inputs/exemples", "--quiet"],
    ["tools/analyze_inputs.py"],
    ["tools/demo_algorithmes.py"],
    ["tools/build_documents.py"],
    ["tools/build_presentation.py"],
    ["tools/build_release.py"],
]


def main() -> int:
    shutil.rmtree(ROOT / "outputs", ignore_errors=True)
    for step in STEPS:
        print(f"\n>>> python {' '.join(step)}", flush=True)
        result = subprocess.run([sys.executable, *step], cwd=ROOT)
        if result.returncode != 0:
            print(f"ÉCHEC : {' '.join(step)} (code {result.returncode})", file=sys.stderr)
            return result.returncode
    print("\nTous les livrables ont été régénérés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
