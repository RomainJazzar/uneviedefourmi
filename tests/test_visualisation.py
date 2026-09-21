"""Les fichiers de visualisation sont produits et cohérents avec la solution."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import main as cli
from ants import load_anthill
from visualization import compute_layout


class OutputFilesTests(unittest.TestCase):
    def test_main_produces_every_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = ROOT / "inputs" / "officiels" / "fourmiliere_quatre.txt"
            stats = cli.run(input_path, Path(tmp), quiet=True)
            case = Path(tmp) / "fourmiliere_quatre"
            for name in ["solution.txt", "graphe.png", "flow_cumule.png", "animation.gif", "stats.json", "matrice_adjacence.csv"]:
                self.assertTrue((case / name).stat().st_size > 0, name)
            frames = sorted((case / "etapes").glob("etape_*.png"))
            self.assertEqual(len(frames), stats["etapes_optimales_T"] + 1)
            with Image.open(case / "animation.gif") as gif:
                self.assertEqual(gif.n_frames, len(frames))
            with Image.open(case / "graphe.png") as png:
                self.assertAlmostEqual(png.width / png.height, 16 / 9, places=2)
            saved = json.loads((case / "stats.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["etapes_optimales_T"], 9)
            text = (case / "solution.txt").read_text(encoding="utf-8")
            self.assertEqual(text.count("+++ E"), 9)

    def test_invalid_file_gives_error_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.txt"
            bad.write_text("f=3\nSv - S1\nS1 => Sd\n", encoding="utf-8")
            self.assertEqual(cli.main([str(bad), "--output", tmp, "--sans-visuels"]), 1)

    def test_summary_tool(self):
        import analyze_inputs

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(analyze_inputs.main([str(ROOT / "inputs" / "officiels"), tmp]), 0)
            for name in ["results.csv", "results.json", "results.md", "resultats.png"]:
                self.assertTrue((Path(tmp) / name).exists(), name)
            rows = json.loads((Path(tmp) / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 9)


class LayoutTests(unittest.TestCase):
    def test_layout_is_deterministic_and_left_to_right(self):
        for path in sorted((ROOT / "inputs" / "officiels").glob("*.txt")):
            with self.subTest(path=path.name):
                anthill = load_anthill(path)
                first, second = compute_layout(anthill), compute_layout(load_anthill(path))
                self.assertEqual(first, second)
                xs = [x for x, _ in first.values()]
                self.assertEqual(first["Sv"][0], min(xs))
                self.assertEqual(first["Sd"][0], max(xs))
                self.assertEqual(set(first), set(anthill.graph.nodes))  # toutes les salles sont dessinées
                points = list(first.values())
                self.assertEqual(len(points), len(set(points)))  # aucune salle superposée


if __name__ == "__main__":
    unittest.main()
