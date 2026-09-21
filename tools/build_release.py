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
    ".gitattributes",
}
INCLUDE_DIRS = {"inputs", "outputs", "tests", "docs", "tools", ".github"}


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if len(rel.parts) == 1:
        return rel.name in INCLUDE_ROOT_FILES
    return rel.parts[0] in INCLUDE_DIRS and "__pycache__" not in rel.parts and not rel.name.startswith("~$")


def main() -> None:
    RELEASE.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    files = [p for p in ROOT.rglob("*") if p.is_file() and should_include(p)]
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(files):
            arcname = (Path("uneviedefourmi") / path.relative_to(ROOT)).as_posix()
            info = zipfile.ZipInfo(arcname, date_time=(2026, 1, 1, 0, 0, 0))  # archive reproductible
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, path.read_bytes(), compresslevel=9)
    print(f"Archive créée : {OUT.relative_to(ROOT)} ({len(files)} fichiers, {OUT.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    main()
