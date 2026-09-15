from __future__ import annotations

"""Génère les documents de soutenance à partir des sources Markdown du repository."""

from html import escape
from pathlib import Path
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt as DocPt
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

NAVY = RGBColor(11, 31, 42)
CREAM = RGBColor(247, 243, 234)
GREEN = RGBColor(112, 145, 92)
GOLD = RGBColor(230, 179, 73)
MUTED = RGBColor(182, 196, 199)
WHITE = RGBColor(255, 255, 255)


def clean_inline(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return text.strip()


def markdown_blocks(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        if not raw:
            yield ("blank", "")
            i += 1
            continue
        if raw.startswith("|"):
            table = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = [clean_inline(x.strip()) for x in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in row):
                    table.append(row)
                i += 1
            if table:
                yield ("table", table)
            continue
        if raw.startswith("### "):
            yield ("h3", clean_inline(raw[4:]))
        elif raw.startswith("## "):
            yield ("h2", clean_inline(raw[3:]))
        elif raw.startswith("# "):
            yield ("h1", clean_inline(raw[2:]))
        elif raw.startswith("> "):
            yield ("quote", clean_inline(raw[2:]))
        elif re.match(r"^\d+\.\s+", raw):
            yield ("number", clean_inline(re.sub(r"^\d+\.\s+", "", raw)))
        elif raw.startswith("- "):
            yield ("bullet", clean_inline(raw[2:]))
        elif raw.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            yield ("code", "\n".join(code))
        elif raw == "---":
            yield ("separator", "")
        else:
            yield ("text", clean_inline(raw))
        i += 1


def build_docx(md_path: Path, out_path: Path, title: str) -> None:
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = 18 * mm
    sec.bottom_margin = 18 * mm
    sec.left_margin = 18 * mm
    sec.right_margin = 18 * mm

    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = DocPt(10.5)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(title)
    r.bold = True
    r.font.size = DocPt(23)
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run("Romain • Lisa • Yannis")
    r2.italic = True
    r2.font.size = DocPt(11)

    first_h1_seen = False
    for kind, value in markdown_blocks(md_path):
        if kind == "h1":
            if not first_h1_seen:
                first_h1_seen = True
                continue
            doc.add_heading(value, level=1)
        elif kind == "h2":
            doc.add_heading(value, level=1)
        elif kind == "h3":
            doc.add_heading(value, level=2)
        elif kind == "bullet":
            doc.add_paragraph(value, style="List Bullet")
        elif kind == "number":
            doc.add_paragraph(value, style="List Number")
        elif kind == "quote":
            p = doc.add_paragraph()
            p.style = doc.styles["Quote"]
            p.add_run(value)
        elif kind == "code":
            p = doc.add_paragraph()
            r = p.add_run(value)
            r.font.name = "Consolas"
            r.font.size = DocPt(9)
        elif kind == "table":
            rows = value
            width = max(len(r) for r in rows)
            table = doc.add_table(rows=len(rows), cols=width)
            table.style = "Table Grid"
            for ri, row in enumerate(rows):
                for ci, cell in enumerate(row):
                    table.cell(ri, ci).text = cell
                    if ri == 0:
                        for run in table.cell(ri, ci).paragraphs[0].runs:
                            run.bold = True
        elif kind == "separator":
            doc.add_paragraph("• • •")
        elif kind == "text" and value:
            doc.add_paragraph(value)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path)


def register_pdf_font() -> str:
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            pdfmetrics.registerFont(TTFont("ProjectSans", str(candidate)))
            return "ProjectSans"
    return "Helvetica"


def build_pdf(md_path: Path, out_path: Path, title: str) -> None:
    font = register_pdf_font()
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "ProjectBody",
        parent=styles["BodyText"],
        fontName=font,
        fontSize=9.3,
        leading=13,
        spaceAfter=5,
    )
    h1 = ParagraphStyle(
        "ProjectH1",
        parent=styles["Heading1"],
        fontName=font,
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#0B1F2A"),
        spaceBefore=10,
        spaceAfter=7,
    )
    h2 = ParagraphStyle(
        "ProjectH2",
        parent=h1,
        fontSize=13,
        leading=16,
    )
    quote = ParagraphStyle(
        "ProjectQuote",
        parent=body,
        leftIndent=12,
        rightIndent=12,
        borderColor=colors.HexColor("#708F5C"),
        borderWidth=1,
        borderPadding=7,
        backColor=colors.HexColor("#F7F3EA"),
    )
    title_style = ParagraphStyle(
        "ProjectTitle",
        parent=h1,
        fontSize=22,
        leading=27,
        alignment=TA_CENTER,
        spaceAfter=5,
    )
    subtitle_style = ParagraphStyle(
        "ProjectSubtitle",
        parent=body,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#5B666A"),
        spaceAfter=14,
    )

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
        author="Romain, Lisa, Yannis",
    )
    story = [
        Paragraph(escape(title), title_style),
        Paragraph("Romain • Lisa • Yannis", subtitle_style),
        Spacer(1, 5),
    ]
    first_h1_seen = False
    for kind, value in markdown_blocks(md_path):
        if kind == "h1":
            if not first_h1_seen:
                first_h1_seen = True
                continue
            story.append(Paragraph(escape(value), h1))
        elif kind == "h2":
            story.append(Paragraph(escape(value), h1))
        elif kind == "h3":
            story.append(Paragraph(escape(value), h2))
        elif kind in {"bullet", "number"}:
            prefix = "• " if kind == "bullet" else "→ "
            story.append(Paragraph(escape(prefix + value), body))
        elif kind == "quote":
            story.append(Paragraph(escape(value), quote))
        elif kind == "code":
            code_style = ParagraphStyle("Code", parent=body, fontName="Courier", fontSize=8.2, backColor=colors.HexColor("#F2F2F2"), leftIndent=7, borderPadding=5)
            story.append(Paragraph(escape(value).replace("\n", "<br/>"), code_style))
        elif kind == "table":
            data = [[Paragraph(escape(cell), body) for cell in row] for row in value]
            table = Table(data, repeatRows=1, hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E7E1D5")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0B1F2A")),
                        ("FONTNAME", (0, 0), (-1, -1), font),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7B2A8")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.extend([table, Spacer(1, 7)])
        elif kind == "separator":
            story.append(Spacer(1, 7))
        elif kind == "text" and value:
            story.append(Paragraph(escape(value), body))
        elif kind == "blank":
            story.append(Spacer(1, 2))
    doc.build(story)


def parse_presentation(path: Path):
    text = path.read_text(encoding="utf-8")
    slides = []
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                slides.append(current)
            heading = clean_inline(line[3:])
            m = re.match(r"(\d+)\s*[—-]\s*(.+)", heading)
            current = {"number": int(m.group(1)) if m else len(slides) + 1, "title": m.group(2) if m else heading, "speaker": "", "body": []}
        elif current is not None:
            stripped = line.strip()
            if stripped.startswith("**Intervenant") or stripped.startswith("**Intervenante"):
                current["speaker"] = clean_inline(stripped.split(":", 1)[1]) if ":" in stripped else ""
            elif stripped and not stripped.startswith("#"):
                if stripped.startswith("|") and "---" in stripped:
                    continue
                current["body"].append(clean_inline(stripped.lstrip("- ")))
    if current:
        slides.append(current)
    return slides


def add_textbox(slide, x, y, w, h, text, size=18, color=WHITE, bold=False, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = "Aptos"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def build_pptx(md_path: Path, out_path: Path) -> None:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    slides = parse_presentation(md_path)

    for data in slides:
        slide = prs.slides.add_slide(blank)
        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = NAVY

        accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.16), prs.slide_height)
        accent.fill.solid(); accent.fill.fore_color.rgb = GREEN; accent.line.fill.background()

        add_textbox(slide, Inches(0.65), Inches(0.52), Inches(10.8), Inches(0.8), data["title"], 27, CREAM, True)
        speaker = data["speaker"] or ("Annexe" if data["number"] == 13 else "Équipe")
        pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(11.45), Inches(0.55), Inches(1.2), Inches(0.42))
        pill.fill.solid(); pill.fill.fore_color.rgb = GREEN; pill.line.fill.background()
        add_textbox(slide, Inches(11.49), Inches(0.59), Inches(1.12), Inches(0.28), speaker, 10, WHITE, True, PP_ALIGN.CENTER)

        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.68), Inches(1.45), Inches(11.95), Inches(5.25))
        card.fill.solid(); card.fill.fore_color.rgb = RGBColor(21, 47, 59); card.line.color.rgb = RGBColor(62, 87, 96)

        body_lines = []
        for line in data["body"]:
            if not line or line.startswith("|"):
                continue
            if line.startswith("**"):
                line = clean_inline(line)
            body_lines.append(line)
        # Keep slides readable: preserve the important first ~13 logical lines.
        body_lines = body_lines[:15]
        box = slide.shapes.add_textbox(Inches(1.05), Inches(1.78), Inches(11.18), Inches(4.58))
        tf = box.text_frame
        tf.clear(); tf.word_wrap = True; tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        for idx, line in enumerate(body_lines):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            p.text = line
            p.font.name = "Aptos"
            p.font.size = Pt(18 if len(body_lines) <= 9 else 15)
            p.font.color.rgb = CREAM
            p.space_after = Pt(8)
            if line.endswith(":") or line.startswith("Objectif") or line.startswith("Question") or line.startswith("Premier T"):
                p.font.bold = True
                p.font.color.rgb = RGBColor(230, 205, 133)

        add_textbox(slide, Inches(0.78), Inches(6.93), Inches(4.3), Inches(0.25), "UNE VIE DE FOURMI • Romain • Lisa • Yannis", 8, MUTED)
        add_textbox(slide, Inches(12.0), Inches(6.91), Inches(0.45), Inches(0.25), str(data["number"]), 9, MUTED, True, PP_ALIGN.RIGHT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)


def main() -> None:
    script_md = DOCS / "Script_oral.md"
    revision_md = DOCS / "Fiche_revision_ultime.md"
    presentation_md = DOCS / "Presentation_contenu.md"

    build_docx(script_md, DOCS / "Script_oral_Une_vie_de_fourmi_Romain_Lisa_Yannis.docx", "SCRIPT ORAL — UNE VIE DE FOURMI")
    build_pdf(script_md, DOCS / "Script_oral_Une_vie_de_fourmi_Romain_Lisa_Yannis.pdf", "SCRIPT ORAL — UNE VIE DE FOURMI")
    build_docx(revision_md, DOCS / "Fiche_revision_ultime_Une_vie_de_fourmi.docx", "FICHE DE RÉVISION ULTIME — UNE VIE DE FOURMI")
    build_pdf(revision_md, DOCS / "Fiche_revision_ultime_Une_vie_de_fourmi.pdf", "FICHE DE RÉVISION ULTIME — UNE VIE DE FOURMI")
    build_pptx(presentation_md, DOCS / "Presentation_Une_vie_de_fourmi_Romain_Lisa_Yannis.pptx")

    print("Documents générés :")
    for path in sorted(DOCS.glob("*.pdf")) + sorted(DOCS.glob("*.docx")) + sorted(DOCS.glob("*.pptx")):
        print(" -", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
