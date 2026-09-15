from __future__ import annotations

"""Wrapper de génération : adapte les unités DOCX/PDF puis appelle le générateur principal."""

from docx.shared import Mm
from reportlab.lib.units import mm as reportlab_mm

import build_documents as b


def main() -> None:
    script_md = b.DOCS / "Script_oral.md"
    revision_md = b.DOCS / "Fiche_revision_ultime.md"
    presentation_md = b.DOCS / "Presentation_contenu.md"

    # python-docx attend une longueur entière (EMU), et non les points flottants de ReportLab.
    b.mm = Mm(1)
    b.build_docx(
        script_md,
        b.DOCS / "Script_oral_Une_vie_de_fourmi_Romain_Lisa_Yannis.docx",
        "SCRIPT ORAL — UNE VIE DE FOURMI",
    )
    b.build_docx(
        revision_md,
        b.DOCS / "Fiche_revision_ultime_Une_vie_de_fourmi.docx",
        "FICHE DE RÉVISION ULTIME — UNE VIE DE FOURMI",
    )

    # ReportLab attend ses propres unités en points.
    b.mm = reportlab_mm
    b.build_pdf(
        script_md,
        b.DOCS / "Script_oral_Une_vie_de_fourmi_Romain_Lisa_Yannis.pdf",
        "SCRIPT ORAL — UNE VIE DE FOURMI",
    )
    b.build_pdf(
        revision_md,
        b.DOCS / "Fiche_revision_ultime_Une_vie_de_fourmi.pdf",
        "FICHE DE RÉVISION ULTIME — UNE VIE DE FOURMI",
    )
    b.build_pptx(
        presentation_md,
        b.DOCS / "Presentation_Une_vie_de_fourmi_Romain_Lisa_Yannis.pptx",
    )

    print("Documents générés avec succès.")


if __name__ == "__main__":
    main()
