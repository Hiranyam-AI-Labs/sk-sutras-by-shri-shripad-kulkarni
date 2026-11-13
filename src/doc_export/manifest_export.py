"""Publication input validation from a frozen human-approved manifest.

Renderers may consume this validated payload; they must not invent missing text.
"""

import json
import uuid
from pathlib import Path
from typing import Any, Dict

from src.orchestration.review_store import fingerprint


SECTION_KEYS = ("sources", "derivation", "sutra_meaning", "commentary",
                "cases_yoga", "dos_donts", "reflection")


def validate_manifest(manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Verify exact content hashes, fifteen gates and all seven substantive sections.

    ``manifest`` is a frozen ReviewStore result, not arbitrary renderer input.
    Returns the validated object; missing/blank sections, mismatched fingerprints
    or non-PASS gates raise ValueError. Inspect unit ID and stored version to debug.
    """
    units = manifest.get("units")
    if not isinstance(units, list) or not units:
        raise ValueError("Approved manifest requires units")
    for entry in units:
        content = entry.get("content")
        if not isinstance(content, dict) or fingerprint(content) != entry.get("content_sha256"):
            raise ValueError("Manifest content fingerprint mismatch")
        sections = content.get("sections")
        if not isinstance(sections, dict) or any(
            not isinstance(sections.get(key), str) or not sections[key].strip()
            for key in SECTION_KEYS
        ):
            raise ValueError(f"Seven substantive sections missing: {entry.get('unit_id')}")
        gates = entry.get("gates")
        if not isinstance(gates, dict) or len(gates) != 15 or any(v != "PASS" for v in gates.values()):
            raise ValueError("All fifteen versioned gates required")
    return manifest


def export_manifest_json(manifest: Dict[str, Any], destination: Path) -> None:
    """Write only a validated frozen manifest to the explicit destination.

    ``destination`` is a caller-selected publication path. Returns None; failed
    validation or write errors propagate. Inspect the destination permissions and
    manifest hash to debug; no filler text or historical repair is performed.
    """
    validated = validate_manifest(manifest)
    destination.write_text(json.dumps(validated, ensure_ascii=False, indent=2), encoding="utf-8")


def export_approved_book(review_store: Any, example_registry: Any, manifest_id: str,
                         docx_path: Path, pdf_path: Path, devanagari_font: Path) -> None:
    """Render a frozen approved manifest to new Word and PDF book files.

    ``manifest_id`` must already be frozen in ReviewStore. Paths are explicit
    and must not exist; the font is a locally installed Unicode font. Returns
    None. Stale approvals, sections, examples, gates, font, and path errors
    block output. Inspect the frozen edition and rendered pages to debug.
    """
    from docx import Document
    from docx.shared import Inches, Pt
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from xml.sax.saxutils import escape

    validated = validate_manifest(review_store.load_manifest(manifest_id, example_registry))
    if docx_path.exists() or pdf_path.exists():
        raise FileExistsError("Publication output already exists; choose a new edition path")
    if not devanagari_font.is_file():
        raise FileNotFoundError(devanagari_font)
    if not docx_path.parent.is_dir() or not pdf_path.parent.is_dir():
        raise FileNotFoundError("Publication output directory must already exist")
    pdfmetrics.registerFont(TTFont("BookDevanagari", str(devanagari_font)))
    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = Inches(.8)
    section.left_margin = section.right_margin = Inches(.9)
    title = doc.add_paragraph("Udyam Sutras", style="Title")
    title.runs[0].font.name = "Nirmala UI"
    intro = doc.add_paragraph("A practical guide for business readers grounded in the approved source and editorial review.")
    intro.style = "Normal"
    footer = section.footer.paragraphs[0]
    footer.text = "Proprietory and Confidential- Hiranyam AI Labs | Powered by Hiranyam AI Labs"
    styles = {
        "title": ParagraphStyle("BookTitle", fontName="BookDevanagari", fontSize=18,
                                leading=25, spaceAfter=18, textColor=colors.black),
        "heading": ParagraphStyle("BookHeading", fontName="BookDevanagari", fontSize=12,
                                  leading=18, spaceBefore=13, spaceAfter=7),
        "body": ParagraphStyle("BookBody", fontName="BookDevanagari", fontSize=10,
                               leading=16, spaceAfter=10),
    }
    story = [Paragraph("Udyam Sutras", styles["title"]),
             Paragraph("A practical guide for business readers grounded in approved sources and human editorial review.", styles["body"])]
    headings = {"sources": "Sources", "derivation": "Derivation to Enterprise",
                "sutra_meaning": "New Sutra and Meaning", "commentary": "Concise Commentary",
                "cases_yoga": "Case Studies and Yoga", "dos_donts": "DOs and DONTs",
                "reflection": "Reflection and Takeaway"}
    for index, entry in enumerate(validated["units"], 1):
        chapter_title = f"Chapter {index}"
        doc.add_heading(chapter_title, level=1)
        story.extend([PageBreak(), Paragraph(chapter_title, styles["title"])])
        for key in SECTION_KEYS:
            doc.add_heading(headings[key], level=2)
            text = entry["content"]["sections"][key]
            doc.add_paragraph(text)
            story.append(Paragraph(headings[key], styles["heading"]))
            for line in text.splitlines():
                if line.strip():
                    story.append(Paragraph(escape(line), styles["body"]))
    docx_temp = docx_path.with_name(f".{docx_path.stem}-{uuid.uuid4().hex}.docx")
    pdf_temp = pdf_path.with_name(f".{pdf_path.stem}-{uuid.uuid4().hex}.pdf")
    try:
        doc.save(docx_temp)
        pdf = SimpleDocTemplate(str(pdf_temp), pagesize=(595.28, 841.89),
                                leftMargin=55, rightMargin=55, topMargin=55)
        pdf.build(story)
        if docx_path.exists() or pdf_path.exists():
            raise FileExistsError("Publication output appeared while rendering")
        docx_temp.replace(docx_path)
        try:
            pdf_temp.replace(pdf_path)
        except Exception:
            docx_path.unlink()
            raise
    finally:
        docx_temp.unlink(missing_ok=True)
        pdf_temp.unlink(missing_ok=True)
