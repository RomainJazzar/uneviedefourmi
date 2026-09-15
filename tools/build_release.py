from __future__ import annotations

"""Construit une archive ZIP prête à télécharger depuis le repository."""

from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
OUT = RELEASE / "Projet_complet_Une_vie_de_fourmi_Romain_Lisa_Yannis.zip"

INCLUDE_ROOT_FILES = {
    "README.md",
    "ants.py",
    "main.py",
    "visualization.py",
    "requirements.txt",
    ".gitignore",
}
INCLUDE_DIRS = {"inputs", "outputs", "tests", "docs", "tools"}


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if len(rel.parts) == 1:
        return rel.name in INCLUDE_ROOT_FILES
    return rel.parts[0] in INCLUDE_DIRS and "__pycache__" not in rel.parts


def main() -> None:
    RELEASE.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    files = [p for p in ROOT.rglob("*") if p.is_file() and should_include(p)]
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(files):
            arcname = Path("uneviedefourmi") / path.relative_to(ROOT)
            zf.write(path, arcname.as_posix())
    print(f"Archive créée : {OUT.relative_to(ROOT)} ({OUT.stat().st_size} octets)")


if __name__ == "__main__":
    main()
