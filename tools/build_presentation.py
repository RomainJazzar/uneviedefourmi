"""Génère la présentation de soutenance (5 minutes, 6 slides + annexes).

    python tools/build_presentation.py

Tous les visuels viennent du code du projet (mêmes fonctions que main.py) et
tous les chiffres viennent des vrais résultats (outputs/summary/results.json,
régénéré si absent). Rien n'est recopié à la main.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

import analyze_inputs
from ants import load_anthill
from visualization import compute_layout, draw_cumulative_flow, draw_graph, draw_step, draw_time_expanded

OUT = ROOT / "docs" / "Presentation_Une_vie_de_fourmi_Romain_Lisa_Yannis.pptx"
ASSETS = ROOT / "build" / "slides"
OFFICIAL = ROOT / "inputs" / "officiels"
DEMO = "fourmiliere_cinq"  # fourmilière montrée pendant la soutenance
HOOK = "salle_d_at-ant"  # image d'accroche
REPO_URL = "github.com/RomainJazzar/uneviedefourmi"

INK = RGBColor(0x0B, 0x1F, 0x2A)
ORANGE = RGBColor(0xEB, 0x68, 0x34)
BLUE = RGBColor(0x2A, 0x78, 0xD6)
MUTED = RGBColor(0x5B, 0x63, 0x6A)
LIGHT = RGBColor(0xF3, 0xF5, 0xF7)
LINE = RGBColor(0xD9, 0xDD, 0xE1)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
DARK_CARD = RGBColor(0x16, 0x32, 0x42)
PALE_TEXT = RGBColor(0xC9, 0xD4, 0xDA)
FONT = "Calibri"

W, H = Inches(13.333), Inches(7.5)


# ---------------------------------------------------------------------------
# Données et images
# ---------------------------------------------------------------------------


def load_results() -> list[dict]:
    path = ROOT / "outputs" / "summary" / "results.json"
    if not path.exists():
        analyze_inputs.main([str(OFFICIAL), str(path.parent)])
    return json.loads(path.read_text(encoding="utf-8"))


def count_tests() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT / "tests"))
    return suite.countTestCases()


def build_assets() -> dict:
    ASSETS.mkdir(parents=True, exist_ok=True)
    assets = {}
    demo = load_anthill(OFFICIAL / f"{DEMO}.txt")
    demo_solution = demo.solve()
    pos = compute_layout(demo)
    draw_graph(demo, ASSETS / "demo_graphe.png", pos=pos, headless=True, dpi=170)
    draw_cumulative_flow(demo, demo_solution, ASSETS / "demo_flow.png", pos=pos, headless=True, dpi=170)
    frames = sorted({0, demo_solution.turns // 3, 2 * demo_solution.turns // 3, demo_solution.turns})
    for t in frames:
        draw_step(demo, demo_solution, t, ASSETS / f"demo_etape_{t:02d}.png", name=DEMO, pos=pos, dpi=130)
    assets.update(demo=demo, demo_solution=demo_solution, frames=frames)

    hook = load_anthill(OFFICIAL / f"{HOOK}.txt")
    hook_solution = hook.solve()
    draw_step(hook, hook_solution, hook_solution.turns // 2, ASSETS / "hook.png", pos=compute_layout(hook), headless=True, dpi=150)
    assets.update(hook=hook, hook_solution=hook_solution)

    subject = load_anthill(ROOT / "inputs" / "exemples" / "cas_simple.txt")  # exemple du sujet
    draw_time_expanded(subject, subject.solve(), ASSETS / "time_expanded.png")
    simple = load_anthill(OFFICIAL / "fourmiliere_zero.txt")
    simple_solution = simple.solve()
    draw_graph(simple, ASSETS / "zero_graphe.png", pos=compute_layout(simple), headless=True, dpi=150)
    assets.update(simple=simple, simple_solution=simple_solution)

    if not (ROOT / "outputs" / "demo_algorithmes" / "shortest_path_vs_flow.png").exists():
        import demo_algorithmes

        demo_algorithmes.run()
    gif = ROOT / "outputs" / DEMO / "animation.gif"
    if not gif.exists():
        import main as cli

        cli.run(OFFICIAL / f"{DEMO}.txt", ROOT / "outputs", quiet=True)
    assets["gif"] = gif
    return assets


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def background(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def text(slide, x, y, w, h, content, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, italic=False, line_spacing=1.0):
    """content : str, ou liste de paragraphes ; un paragraphe = str ou liste de (texte, options)."""
    box = slide.shapes.add_textbox(x, y, w, h)
    frame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
    frame.vertical_anchor = anchor
    paragraphs = content if isinstance(content, list) else [content]
    for i, para in enumerate(paragraphs):
        p = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        runs = para if isinstance(para, list) else [(para, {})]
        for chunk, opts in runs:
            run = p.add_run()
            run.text = chunk
            f = run.font
            f.name = FONT
            f.size = Pt(opts.get("size", size))
            f.bold = opts.get("bold", bold)
            f.italic = opts.get("italic", italic)
            f.color.rgb = opts.get("color", color)
        if isinstance(para, list) and para and "space_after" in para[0][1]:
            p.space_after = Pt(para[0][1]["space_after"])
    return box


def shape(slide, kind, x, y, w, h, fill=None, line=None, radius=None, line_width=1.0):
    s = slide.shapes.add_shape(kind, x, y, w, h)
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(line_width)
    if radius is not None and kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.shadow.inherit = False
    s.text_frame.margin_left = s.text_frame.margin_right = 0
    return s


def card(slide, x, y, w, h, fill=LIGHT, line=None):
    return shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill=fill, line=line, radius=0.08)


def badge(slide, x, y, label, fill=ORANGE, color=WHITE, d=Inches(0.5), size=18):
    c = shape(slide, MSO_SHAPE.OVAL, x, y, d, d, fill=fill)
    tf = c.text_frame
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(size), True, color
    return c


def picture(slide, path, x, y, w, h, align="center"):
    """Image entière, sans déformation, centrée dans la boîte (x, y, w, h)."""
    with Image.open(path) as im:
        ratio = im.width / im.height
    if w / h > ratio:
        pw, ph = int(h * ratio), h
    else:
        pw, ph = w, int(w / ratio)
    px = x + (w - pw) // 2 if align == "center" else x
    py = y + (h - ph) // 2
    return slide.shapes.add_picture(str(path), px, py, pw, ph)


def speaker_chip(slide, who, seconds, dark=False):
    label = f"{who} · {seconds}"
    chip = shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, W - Inches(2.55), Inches(0.42), Inches(2.1), Inches(0.42),
                 fill=DARK_CARD if dark else LIGHT, radius=0.5)
    tf = chip.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name, r.font.size, r.font.bold = FONT, Pt(13), True
    r.font.color.rgb = PALE_TEXT if dark else MUTED


def title(slide, content, dark=False, size=36, subtitle=None, width=Inches(10.2)):
    text(slide, Inches(0.6), Inches(0.38), width, Inches(0.8), content, size=size, bold=True,
         color=WHITE if dark else INK, anchor=MSO_ANCHOR.TOP)
    if subtitle:
        text(slide, Inches(0.6), Inches(1.12), width, Inches(0.45), subtitle, size=17,
             color=PALE_TEXT if dark else MUTED)


def footer(slide, number, dark=False):
    text(slide, Inches(0.6), H - Inches(0.42), Inches(6), Inches(0.3), "Une vie de fourmi · Romain · Lisa · Yannis",
         size=10, color=PALE_TEXT if dark else MUTED)
    text(slide, W - Inches(1.1), H - Inches(0.42), Inches(0.5), Inches(0.3), str(number), size=10,
         color=PALE_TEXT if dark else MUTED, align=PP_ALIGN.RIGHT)


def arrow(slide, x1, y1, x2, y2, color=MUTED, width=2.0):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    c.line.color.rgb = color
    c.line.width = Pt(width)
    line = c.line._get_or_add_ln()
    tail = line.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", {"type": "triangle", "w": "med", "len": "med"})
    line.append(tail)
    return c


def notes(slide, content):
    slide.notes_slide.notes_text_frame.text = content


def annex_label(slide):
    chip = shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, W - Inches(2.05), Inches(0.42), Inches(1.6), Inches(0.42), fill=LIGHT, radius=0.5)
    p = chip.text_frame.paragraphs[0]
    chip.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = "ANNEXE"
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(13), True, MUTED


def table(slide, x, y, w, rows, col_widths, size=14, highlight=(), row_h=Inches(0.42), header_fill=INK, left=False):
    shape_ = slide.shapes.add_table(len(rows), len(rows[0]), x, y, w, row_h * len(rows))
    tbl = shape_.table
    tbl.first_row = True
    for i, cw in enumerate(col_widths):
        tbl.columns[i].width = cw
    for r, row in enumerate(rows):
        tbl.rows[r].height = row_h
        for c, value in enumerate(row):
            cell = tbl.cell(r, c)
            cell.margin_left = cell.margin_right = Inches(0.1)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            if r == 0:
                cell.fill.fore_color.rgb = header_fill
            elif r in highlight:
                cell.fill.fore_color.rgb = RGBColor(0xFD, 0xE9, 0xE0)
            else:
                cell.fill.fore_color.rgb = WHITE if r % 2 else LIGHT
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if c == 0 or left else PP_ALIGN.CENTER
            run = p.add_run()
            run.text = str(value)
            run.font.name = FONT
            run.font.size = Pt(size)
            run.font.bold = r == 0 or (r in highlight and c == len(row) - 1)
            run.font.color.rgb = WHITE if r == 0 else INK
    return shape_


# ---------------------------------------------------------------------------
# Slides principales
# ---------------------------------------------------------------------------


def slide_probleme(prs, a):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, INK)
    speaker_chip(s, "Romain", "40 s", dark=True)
    text(s, Inches(0.6), Inches(0.5), Inches(6), Inches(0.35), "UNE VIE DE FOURMI", size=14, bold=True, color=ORANGE)
    text(s, Inches(0.6), Inches(0.95), Inches(5.3), Inches(1.9), "Faire arriver toute la colonie le plus vite possible",
         size=38, bold=True, color=WHITE, line_spacing=0.95)
    rules = [
        ("1", "Plusieurs fourmis en parallèle", "toutes partent de Sv, toutes doivent finir dans Sd"),
        ("2", "Salles à capacité limitée", "1 fourmi par défaut, X pour une salle SN{X}"),
        ("3", "Minimum d'étapes", "c'est l'arrivée de la dernière fourmi qui compte"),
    ]
    for i, (n, head, sub) in enumerate(rules):
        y = Inches(3.15) + i * Inches(0.95)
        badge(s, Inches(0.6), y, n)
        text(s, Inches(1.3), y - Inches(0.04), Inches(4.6), Inches(0.4), head, size=20, bold=True, color=WHITE)
        text(s, Inches(1.3), y + Inches(0.36), Inches(4.6), Inches(0.35), sub, size=14, color=PALE_TEXT)
    text(s, Inches(0.6), Inches(6.2), Inches(5.6), Inches(0.8),
         [[("Ce n'est pas un problème de chemin.", {"color": WHITE})], [("C'est un problème de trafic.", {"color": ORANGE, "bold": True})]],
         size=19, italic=True)
    card(s, Inches(6.25), Inches(1.0), Inches(6.7), Inches(5.55), fill=RGBColor(0xFC, 0xFC, 0xFB))
    picture(s, ASSETS / "hook.png", Inches(6.35), Inches(1.1), Inches(6.5), Inches(5.35))
    f, t = a["hook"].ant_count, a["hook_solution"].turns
    text(s, Inches(6.25), Inches(6.65), Inches(6.7), Inches(0.35),
         f"Vraie fourmilière officielle ({HOOK}) : {f} fourmis, étape {t // 2} sur {t}", size=12, color=PALE_TEXT, align=PP_ALIGN.CENTER)
    notes(s, SCRIPT[1])


def slide_donnees(prs, a, rows):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, WHITE)
    speaker_chip(s, "Romain", "40 s")
    demo = a["demo"]
    row = next(r for r in rows if r["fichier"] == f"{DEMO}.txt")
    title(s, "Un fichier officiel devient un graphe", subtitle=f"{DEMO}.txt, tel qu'il est fourni par le sujet")
    # extrait brut du fichier
    raw = (OFFICIAL / f"{DEMO}.txt").read_text(encoding="utf-8").splitlines()
    excerpt = [raw[0], raw[1], raw[2], raw[9], "…", raw[15], raw[19], raw[22], "…"]
    card(s, Inches(0.6), Inches(1.75), Inches(2.3), Inches(3.0), fill=INK)
    text(s, Inches(0.8), Inches(1.9), Inches(2.0), Inches(3.3), [[(l.rstrip(), {})] for l in excerpt], size=15, color=WHITE, line_spacing=1.05)
    s.shapes[-1].text_frame.paragraphs[0].runs[0].font.name = "Consolas"
    for p in s.shapes[-1].text_frame.paragraphs:
        for r in p.runs:
            r.font.name = "Consolas"
    # stats
    stats = [
        (str(row["fourmis"]), "fourmis"),
        (str(row["salles_intermediaires"]), "salles"),
        (str(row["tunnels"]), "tunnels"),
        (f"{row['capacite_min']} à {row['capacite_max']}", "capacités"),
    ]
    for i, (value, label) in enumerate(stats):
        y = Inches(5.05) + (i // 2) * Inches(0.8)
        x = Inches(0.6) + (i % 2) * Inches(1.2)
        text(s, x, y, Inches(1.2), Inches(0.45), value, size=24, bold=True, color=ORANGE)
        text(s, x, y + Inches(0.42), Inches(1.2), Inches(0.3), label, size=12, color=MUTED)
    arrow(s, Inches(3.0), Inches(3.5), Inches(3.45), Inches(3.5), color=ORANGE, width=3)
    picture(s, ASSETS / "demo_graphe.png", Inches(3.5), Inches(1.55), Inches(9.3), Inches(5.0))
    # lecture
    legend = [("salle", "= sommet"), ("tunnel", "= arête"), ("S1 { 8 }", "= 8 fourmis à la fois")]
    x = Inches(3.9)
    for head, rest in legend:
        text(s, x, Inches(6.62), Inches(3.0), Inches(0.35), [[(head + " ", {"bold": True, "color": INK}), (rest, {"color": MUTED})]], size=15)
        x += Inches(2.55)
    footer(s, 2)
    notes(s, SCRIPT[2])


def slide_algo(prs, a, rows):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, WHITE)
    speaker_chip(s, "Lisa", "55 s")
    title(s, "Comment l'algorithme réfléchit", subtitle="On ne cherche pas un chemin : on teste un nombre d'étapes T")
    demo_row = next(r for r in rows if r["fichier"] == f"{DEMO}.txt")
    steps = [
        ("1", "BFS", "distance minimale d : aucune arrivée avant d"),
        ("2", "Graphe déplié dans le temps", "une copie de chaque salle à chaque instant t"),
        ("3", "Max-flow", "combien de fourmis peuvent arriver en T étapes ?"),
    ]
    x0, y0, step_h = Inches(0.6), Inches(1.8), Inches(0.98)
    for i, (n, head, sub) in enumerate(steps):
        y = y0 + i * step_h
        badge(s, x0, y, n, fill=INK)
        text(s, x0 + Inches(0.65), y - Inches(0.03), Inches(4.5), Inches(0.4), head, size=19, bold=True)
        text(s, x0 + Inches(0.65), y + Inches(0.36), Inches(4.5), Inches(0.5), sub, size=14, color=MUTED)
    # décision
    y = y0 + 3 * step_h
    badge(s, x0, y, "?", fill=ORANGE)
    text(s, x0 + Inches(0.65), y - Inches(0.03), Inches(4.1), Inches(0.4), "Les F fourmis passent ?", size=19, bold=True)
    no = card(s, x0 + Inches(0.65), y + Inches(0.5), Inches(1.9), Inches(0.62), fill=LIGHT)
    text(s, x0 + Inches(0.75), y + Inches(0.5), Inches(1.75), Inches(0.62), [[("NON", {"bold": True, "color": INK}), ("  →  T + 1", {"color": MUTED})]], size=16, anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    yes = card(s, x0 + Inches(2.7), y + Inches(0.5), Inches(2.1), Inches(0.62), fill=ORANGE)
    text(s, x0 + Inches(2.75), y + Inches(0.5), Inches(2.0), Inches(0.62), [[("OUI", {"bold": True}), ("  →  optimum", {})]], size=16, color=WHITE, anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.CENTER)
    text(s, x0, Inches(6.35), Inches(4.9), Inches(0.7),
         [[("BFS", {"bold": True, "color": INK}), (" donne la borne minimale ; le ", {}), ("max-flow", {"bold": True, "color": INK}), (" organise ensuite toute la colonie.", {})]],
         size=14, color=MUTED)

    # droite : graphe temporel + courbe max-flow(T)
    text(s, Inches(5.9), Inches(1.7), Inches(6.9), Inches(0.35), [[("Le graphe déplié ", {"bold": True, "color": INK}), ("· exemple du sujet, 3 fourmis : flèche = attendre ou traverser un tunnel", {"color": MUTED})]], size=13)
    picture(s, ASSETS / "time_expanded.png", Inches(5.9), Inches(2.05), Inches(6.9), Inches(2.5))
    flows = demo_row["horizons_testes"]
    text(s, Inches(5.9), Inches(4.62), Inches(6.9), Inches(0.35), [[(f"Max-flow selon T ", {"bold": True, "color": INK}), (f"· {DEMO}, F = {demo_row['fourmis']} : le premier T qui atteint F est le minimum", {"color": MUTED})]], size=13)
    data = CategoryChartData()
    data.categories = [f"T={f['T']}" for f in flows]
    data.add_series("fourmis arrivées au maximum", [f["max_fourmis"] for f in flows])
    gframe = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(5.9), Inches(4.95), Inches(6.9), Inches(2.1), data)
    chart = gframe.chart
    chart.has_legend = False
    chart.has_title = False
    chart.font.name = FONT
    chart.font.size = Pt(12)
    plot = chart.plots[0]
    plot.gap_width = 45
    plot.has_data_labels = True
    labels = plot.data_labels
    labels.position = XL_LABEL_POSITION.OUTSIDE_END
    labels.font.size = Pt(13)
    labels.font.bold = True
    labels.font.color.rgb = INK
    series = plot.series[0]
    for i, f in enumerate(flows):
        point = series.points[i]
        point.format.fill.solid()
        point.format.fill.fore_color.rgb = ORANGE if f["max_fourmis"] >= demo_row["fourmis"] else RGBColor(0xB7, 0xC3, 0xCC)
    va = chart.value_axis
    va.visible = False
    va.has_major_gridlines = False
    va.maximum_scale = demo_row["fourmis"] * 1.25
    va.minimum_scale = 0
    ca = chart.category_axis
    ca.tick_labels.font.size = Pt(12)
    ca.tick_labels.font.color.rgb = MUTED
    ca.format.line.color.rgb = LINE
    footer(s, 3)
    notes(s, SCRIPT[3])


def slide_demo(prs, a, rows):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, WHITE)
    speaker_chip(s, "Lisa → Yannis", "55 s")
    row = next(r for r in rows if r["fichier"] == f"{DEMO}.txt")
    title(s, "Voir les fourmis circuler", subtitle=f"{DEMO} · graphe complet à chaque étape · orange = déplacements de l'étape")
    picture(s, a["gif"], Inches(0.45), Inches(1.7), Inches(7.7), Inches(5.3))
    x = Inches(8.35)
    card(s, x, Inches(1.7), Inches(4.5), Inches(1.6), fill=INK)
    text(s, x + Inches(0.3), Inches(1.8), Inches(4.0), Inches(0.8), [[(f"{row['fourmis']} fourmis", {"color": WHITE}), ("  en  ", {"color": PALE_TEXT, "size": 20}), (str(row["etapes_optimales_T"]), {"color": ORANGE})]], size=32, bold=True)
    text(s, x + Inches(0.3), Inches(2.5), Inches(4.0), Inches(0.8), [[("étapes : le minimum possible", {})], [("premier T réalisable = optimum", {"color": ORANGE, "bold": True})]], size=16, color=PALE_TEXT)
    text(s, x, Inches(3.5), Inches(4.5), Inches(0.35), [[("Trafic cumulé ", {"bold": True, "color": INK}), ("· épaisseur = passages", {"color": MUTED})]], size=14)
    picture(s, ASSETS / "demo_flow.png", x, Inches(3.85), Inches(4.5), Inches(2.6))
    text(s, x, Inches(6.55), Inches(4.5), Inches(0.4), f"Goulot : au plus {row['debit_max_par_etape']} arrivées par étape (coupe minimale)", size=12, color=MUTED)
    footer(s, 4)
    notes(s, SCRIPT[4])


def slide_validation(prs, a, rows, n_tests):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, WHITE)
    speaker_chip(s, "Yannis", "45 s")
    title(s, f"{len(rows)} / {len(rows)} fourmilières officielles résolues", subtitle="Même programme, aucun réglage par fichier")
    header = ["fichier", "fourmis", "salles", "tunnels", "d (BFS)", "T optimal"]
    body = [[r["fichier"].removesuffix(".txt"), r["fourmis"], r["salles_intermediaires"], r["tunnels"], r["distance_min_d"], r["etapes_optimales_T"]] for r in rows]
    highlight = {i + 1 for i, r in enumerate(rows) if r["fichier"] in ("fourmiliere_zero.txt", f"{DEMO}.txt", "salle_d_at-ant.txt")}
    widths = [Inches(3.0), Inches(1.05), Inches(0.95), Inches(1.0), Inches(1.05), Inches(1.3)]
    table(s, Inches(0.6), Inches(1.75), sum(widths, Emu(0)), [header] + body, widths, size=15, highlight=highlight, row_h=Inches(0.47))
    x = Inches(9.35)
    big = max(rows, key=lambda r: r["fourmis"])
    cards = [
        (f"{big['fourmis']} → {big['etapes_optimales_T']}", f"{big['fourmis']} fourmis en {big['etapes_optimales_T']} étapes ({big['fichier'].removesuffix('.txt')})"),
        ("400 / 400", "graphes aléatoires : même minimum que\nl'exploration exhaustive (BFS sur les états)"),
        (str(n_tests), "tests automatiques : parseur, règles,\ncas limites, optimalité"),
    ]
    for i, (value, label) in enumerate(cards):
        y = Inches(1.75) + i * Inches(1.62)
        card(s, x, y, Inches(3.5), Inches(1.45), fill=LIGHT)
        text(s, x + Inches(0.25), y + Inches(0.12), Inches(3.1), Inches(0.6), value, size=30, bold=True, color=ORANGE if i == 0 else INK)
        text(s, x + Inches(0.25), y + Inches(0.75), Inches(3.1), Inches(0.65), label, size=12.5, color=MUTED)
    footer(s, 5)
    notes(s, SCRIPT[5])


def slide_conclusion(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, INK)
    speaker_chip(s, "Yannis", "25 s", dark=True)
    text(s, Inches(0.6), Inches(0.5), Inches(8), Inches(0.8), "Ce qu'on a construit", size=36, bold=True, color=WHITE)
    blocks = [
        ("CORRECT", "capacités et simultanéité respectées, vérifiées sur chaque étape"),
        ("OPTIMAL", "minimum d'étapes prouvé par le max-flow et recoupé par recherche exhaustive"),
        ("VISUEL", "graphe complet, étapes, GIF et trafic cumulé générés automatiquement"),
    ]
    for i, (head, sub) in enumerate(blocks):
        x = Inches(0.6) + i * Inches(4.1)
        card(s, x, Inches(1.7), Inches(3.85), Inches(2.1), fill=DARK_CARD)
        text(s, x + Inches(0.3), Inches(1.95), Inches(3.3), Inches(0.5), head, size=24, bold=True, color=ORANGE)
        text(s, x + Inches(0.3), Inches(2.6), Inches(3.3), Inches(1.1), sub, size=16, color=PALE_TEXT)
    text(s, Inches(0.6), Inches(4.35), Inches(12.1), Inches(1.4),
         [[("Le plus court chemin optimise une fourmi.", {"color": PALE_TEXT})], [("Notre solution optimise toute la colonie.", {"color": WHITE, "bold": True})]],
         size=30, line_spacing=1.1)
    text(s, Inches(0.6), Inches(6.0), Inches(6), Inches(0.6), "Questions ?", size=28, bold=True, color=ORANGE)
    text(s, Inches(6.8), Inches(6.15), Inches(5.9), Inches(0.4), REPO_URL, size=14, color=PALE_TEXT, align=PP_ALIGN.RIGHT)
    notes(s, SCRIPT[6])


# ---------------------------------------------------------------------------
# Annexes
# ---------------------------------------------------------------------------


def annex_base(prs, heading, number, subtitle=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    background(s, WHITE)
    annex_label(s)
    title(s, heading, size=30, subtitle=subtitle)
    footer(s, number)
    return s


def annexes(prs, a, rows, n_tests):
    n = 7
    # A1 architecture
    s = annex_base(prs, "Architecture du code", n, "Chaque fichier a un rôle ; tout est relancé par la CI GitHub Actions")
    boxes = [
        ("inputs/", "officiels/ (9 fichiers)\nexemples/", Inches(0.6)),
        ("ants.py", "lecture du fichier\nmodèle Anthill\nBFS · graphe temporel\nmax-flow · min-cost\ndécomposition · vérification", Inches(3.55)),
        ("main.py", "résout un fichier\nou un dossier\nécrit les sorties", Inches(6.5)),
        ("outputs/", "solution.txt · stats.json\ngraphe.png · flow_cumule.png\netapes/*.png · animation.gif", Inches(9.45)),
    ]
    for head, body, x in boxes:
        card(s, x, Inches(2.0), Inches(2.6), Inches(2.6), fill=LIGHT)
        text(s, x + Inches(0.2), Inches(2.15), Inches(2.3), Inches(0.5), head, size=20, bold=True, color=ORANGE if head == "ants.py" else INK)
        text(s, x + Inches(0.2), Inches(2.7), Inches(2.3), Inches(1.8), body, size=13.5, color=MUTED)
    for x in (Inches(3.25), Inches(6.2), Inches(9.15)):
        arrow(s, x, Inches(3.3), x + Inches(0.28), Inches(3.3), color=ORANGE, width=2.5)
    small = [
        ("visualization.py", "layout déterministe, frames, GIF, trafic cumulé"),
        ("tools/analyze_inputs.py", "tableau et graphique des 9 fichiers"),
        ("tests/", f"{n_tests} tests : parseur, solveur, officiels, BFS exhaustif"),
        ("tools/build_*.py", "présentation, script, fiche, ZIP"),
    ]
    for i, (head, body) in enumerate(small):
        x = Inches(0.6) + i * Inches(3.1)
        text(s, x, Inches(5.1), Inches(2.95), Inches(1.2), [[(head, {"bold": True, "color": INK, "size": 15})], [(body, {"color": MUTED})]], size=13)
    n += 1

    # A2 contre-exemple : plus court chemin seul vs max-flow
    s = annex_base(prs, "Pourquoi pas simplement BFS ou Dijkstra ?", n,
                   "Contre-exemple : 3 fourmis, capacité 1, un chemin de longueur 2 et un de longueur 3")
    picture(s, ROOT / "outputs" / "demo_algorithmes" / "shortest_path_vs_flow.png", Inches(0.5), Inches(1.6), Inches(8.6), Inches(4.85))
    explanations = [
        ("BFS", "utile pour trouver la distance minimale (ici d = 2) : on l'utilise."),
        ("Dijkstra", "inutile ici car tous les tunnels coûtent 1 : même résultat que BFS."),
        ("Max-flow temporel", "répartit plusieurs fourmis sur plusieurs chemins en respectant les capacités."),
    ]
    for i, (head, body) in enumerate(explanations):
        y = Inches(1.75) + i * Inches(1.6)
        card(s, Inches(9.35), y, Inches(3.45), Inches(1.4), fill=RGBColor(0xFD, 0xE9, 0xE0) if i == 2 else LIGHT)
        text(s, Inches(9.55), y + Inches(0.15), Inches(3.1), Inches(1.15),
             [[(head, {"bold": True, "color": ORANGE if i == 2 else INK, "size": 17})], [(body, {})]], size=13.5, color=MUTED)
    text(s, Inches(0.6), Inches(6.55), Inches(12.2), Inches(0.4),
         "Plus court chemin individuel ≠ temps minimum pour toute la colonie : d'où le graphe temporel et le max-flow.",
         size=14, bold=True, color=INK)
    n += 1

    # A3 tableau comparatif
    s = annex_base(prs, "Chaque algorithme répond à un problème différent", n,
                   "Aucun n'est « mauvais » : on utilise celui qui correspond à la question posée")
    rows_algo = [
        ["Algorithme", "Sert à quoi ici ?", "Utilisé ?"],
        ["BFS", "distance minimale / chemins non pondérés", "OUI : borne basse d (ants.bfs_distances)"],
        ["DFS", "exploration, mais pas de minimum garanti", "NON"],
        ["Dijkstra", "plus court chemin pondéré", "NON, inutile ici (tous les tunnels valent 1)"],
        ["Floyd-Warshall", "toutes les distances entre toutes les paires", "NON"],
        ["Edmonds-Karp", "max-flow via BFS dans le graphe résiduel", "OUI : F fourmis en T étapes ?"],
        ["Min-cost flow", "départager les solutions optimales", "OUI : à T fixé, trajets propres"],
    ]
    table(s, Inches(0.6), Inches(1.75), Inches(12.1), rows_algo, [Inches(2.6), Inches(5.0), Inches(4.5)], size=16, row_h=Inches(0.62), highlight={1, 5, 6}, left=True)
    n += 1

    # A3 graphe temporel et node splitting
    s = annex_base(prs, "Graphe temporel et découpage des salles", n, "Transformer « position + temps » en un problème de flot statique")
    picture(s, ASSETS / "time_expanded.png", Inches(0.5), Inches(1.75), Inches(6.9), Inches(4.0))
    items = [
        ("Sommets", "(salle, t) pour chaque salle et chaque instant 0 … T"),
        ("Attendre", "(salle, t) → (salle, t+1)"),
        ("Se déplacer", "(a, t) → (b, t+1) si le tunnel a–b existe ; capacité illimitée"),
        ("Capacité SN{X}", "chaque (salle, t) est coupé en entrée → sortie de capacité X : c'est le node splitting"),
        ("Sv et Sd", "capacité F : jamais limitants ; Sd absorbant (on n'en ressort pas)"),
        ("Une unité de flot", "= une fourmi ; flot de valeur F = toutes les fourmis arrivent en T étapes"),
    ]
    for i, (head, body) in enumerate(items):
        y = Inches(1.8) + i * Inches(0.82)
        text(s, Inches(7.7), y, Inches(5.1), Inches(0.8), [[(head, {"bold": True, "color": INK, "size": 16})], [(body, {"color": MUTED})]], size=13.5)
    text(s, Inches(0.6), Inches(6.2), Inches(6.8), Inches(0.6), "Premier T faisable = optimum : si T marche, T+1 marche aussi (on attend dans Sd), et on teste T = d, d+1, … dans l'ordre.", size=13, color=INK)
    n += 1

    # A4 objectifs du min-cost
    s = annex_base(prs, "Min-cost flow : des trajets propres, sans changer T", n, "Optimisation lexicographique : chaque niveau pèse plus que tous les suivants réunis")
    rows_obj = [
        ["Priorité", "Objectif", "Comment", "Poids"],
        ["1", "minimiser T (dernière arrivée)", "déjà fixé par le max-flow", "—"],
        ["2", "arrivées au plus tôt", "chaque étape hors de Sd coûte", "M²"],
        ["3", "le moins de mouvements", "chaque déplacement coûte en plus", "M"],
        ["4", "pas de pas inutiles", "un pas qui ne rapproche pas de Sd coûte", "1"],
    ]
    table(s, Inches(0.6), Inches(1.75), Inches(12.1), rows_obj, [Inches(1.3), Inches(3.8), Inches(5.3), Inches(1.7)], size=16, row_h=Inches(0.58))
    text(s, Inches(0.6), Inches(4.95), Inches(12.1), Inches(1.5), [
        [("M = F × T + 1. ", {"bold": True, "color": INK}), ("Chaque objectif compte au plus F × T unités, donc une seule unité d'un niveau coûte plus que le maximum de tous les niveaux suivants : aucun compromis possible.", {})],
        [("Avant la correction ", {"bold": True, "color": INK}), ("un pas en arrière pouvait coûter moins cher qu'une attente : 75 allers-retours A→B→A sur fourmiliere_3D, 188 sur salle_d_at-ant. Aujourd'hui : 0, et 30 % de mouvements en moins.", {})],
    ], size=15, color=MUTED)
    n += 1

    # A5 matrice d'adjacence
    s = annex_base(prs, "Matrice d'adjacence", n, "fourmiliere_zero : 1 = un tunnel relie les deux salles (matrice symétrique)")
    nodes, matrix = a["simple"].adjacency_matrix()
    table(s, Inches(0.6), Inches(1.9), Inches(5.6), [[""] + nodes] + [[nodes[i]] + row for i, row in enumerate(matrix)], [Inches(1.2)] + [Inches(1.1)] * len(nodes), size=18, row_h=Inches(0.6))
    picture(s, ASSETS / "zero_graphe.png", Inches(6.6), Inches(1.7), Inches(6.2), Inches(3.8))
    text(s, Inches(0.6), Inches(5.4), Inches(5.6), Inches(1.2), "Exportée pour chaque fourmilière dans outputs/<nom>/matrice_adjacence.csv. NetworkX stocke le graphe en listes d'adjacence, plus économes pour des graphes peu denses.", size=13.5, color=MUTED)
    n += 1

    # A6 complexité
    s = annex_base(prs, "Complexité et temps mesurés", n, "Taille du graphe temporel pour un horizon T, avec n salles et m tunnels")
    text(s, Inches(0.6), Inches(1.8), Inches(5.6), Inches(3.8), [
        [("Sommets", {"bold": True, "color": INK, "size": 17})], [("2 · n · (T + 1)", {})],
        [("Arcs", {"bold": True, "color": INK, "size": 17})], [("n · (T + 1) + T · (n + 2m)", {})],
        [("Edmonds-Karp", {"bold": True, "color": INK, "size": 17})], [("O(V · E²) en théorie ; ici au plus F augmentations", {})],
        [("Recherche de T", {"bold": True, "color": INK, "size": 17})], [("linéaire : T − d + 1 max-flows. La recherche binaire est valide (faisabilité monotone) mais plus lente ici : elle teste de très grands T (jusqu'à d + F − 1).", {})],
    ], size=14.5, color=MUTED)
    rows_t = [["fichier", "F", "T", "temps"]] + [[r["fichier"].removesuffix(".txt"), r["fourmis"], r["etapes_optimales_T"], f"{r['temps_ms']:.0f} ms"] for r in rows]
    table(s, Inches(6.7), Inches(1.75), Inches(6.0), rows_t, [Inches(3.2), Inches(0.9), Inches(0.9), Inches(1.0)], size=13, row_h=Inches(0.43))
    n += 1

    # A7 tests
    s = annex_base(prs, "Comment on sait que c'est juste", n, f"{n_tests} tests automatiques, lancés à chaque push par GitHub Actions")
    groups = [
        ("Parseur", "S1 { 5 }, f=50, F = 100, BOM, CRLF, tabulations, commentaires ; erreurs avec numéro de ligne ; capacités contradictoires"),
        ("Règles", "capacités à chaque instant, tunnels existants, départ Sv, arrivée Sd, Sd absorbant, nombre exact de fourmis"),
        ("Topologies", "cul-de-sac, cycle, tunnel direct Sv–Sd, grosse capacité, goulot, F = 100"),
        ("Optimalité", "max-flow insuffisant à T − 1 ; 400 graphes aléatoires comparés à une recherche exhaustive (BFS sur les états)"),
        ("Qualité", "aucun aller-retour A→B→A, arrivées au plus tôt, résultat identique d'une exécution à l'autre"),
        ("Contre-épreuve", "3 solveurs volontairement faux sont détectés par la recherche exhaustive (136, 77 et 101 cas sur 400)"),
    ]
    for i, (head, body) in enumerate(groups):
        col, line = i % 2, i // 2
        x, y = Inches(0.6) + col * Inches(6.15), Inches(1.8) + line * Inches(1.6)
        card(s, x, y, Inches(5.95), Inches(1.42), fill=LIGHT)
        text(s, x + Inches(0.25), y + Inches(0.15), Inches(5.5), Inches(1.2), [[(head, {"bold": True, "color": INK, "size": 17})], [(body, {})]], size=13.5, color=MUTED)
    n += 1

    # A8 résultats complets
    s = annex_base(prs, "Résultats complets", n)
    picture(s, ROOT / "outputs" / "summary" / "resultats.png", Inches(0.6), Inches(1.25), Inches(12.1), Inches(5.8))
    n += 1

    # A9 frames de secours
    s = annex_base(prs, "Si le GIF ne s'anime pas : les étapes clés", n, f"{DEMO} · mêmes positions sur chaque image")
    frames = a["frames"]
    for i, t in enumerate(frames[:4]):
        col, line = i % 2, i // 2
        picture(s, ASSETS / f"demo_etape_{t:02d}.png", Inches(0.6) + col * Inches(6.15), Inches(1.65) + line * Inches(2.72), Inches(5.95), Inches(2.62))


# ---------------------------------------------------------------------------
# Notes orateur (reprennent le script oral)
# ---------------------------------------------------------------------------

def load_script() -> dict[int, str]:
    """Notes orateur = texte à dire de chaque slide, lu dans docs/Script_oral_5min.md."""
    notes_by_slide: dict[int, str] = {}
    current = None
    for line in (ROOT / "docs" / "Script_oral_5min.md").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^## Slide (\d+) — (.+)$", line)
        if match:
            current = int(match.group(1))
            notes_by_slide[current] = match.group(2).upper() + "\n"
        elif line.startswith("## "):
            current = None
        elif current and line.startswith(">"):
            notes_by_slide[current] += re.sub(r"\*\*", "", line[1:].strip()) + "\n"
        elif current and line.startswith("**Geste"):
            notes_by_slide[current] += "\n" + re.sub(r"\*\*", "", line) + "\n"
    return notes_by_slide


SCRIPT: dict[int, str] = {}


def main() -> None:
    SCRIPT.update(load_script())
    rows = load_results()
    n_tests = count_tests()
    a = build_assets()
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    prs.core_properties.title = "Une vie de fourmi"
    prs.core_properties.author = "Romain, Lisa, Yannis"
    slide_probleme(prs, a)
    slide_donnees(prs, a, rows)
    slide_algo(prs, a, rows)
    slide_demo(prs, a, rows)
    slide_validation(prs, a, rows, n_tests)
    slide_conclusion(prs)
    annexes(prs, a, rows, n_tests)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"Présentation : {OUT.relative_to(ROOT)} ({len(prs.slides)} slides, {n_tests} tests comptés)")


if __name__ == "__main__":
    main()
