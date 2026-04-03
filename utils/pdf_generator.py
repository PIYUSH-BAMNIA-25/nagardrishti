"""
pdf_generator.py — Complaint PDF Report Generator

Uses ReportLab to create a professionally formatted PDF containing:
    • NagarDrishti header & branding
    • Complaint metadata (date, severity, location)
    • Full complaint letter text
    • Embedded evidence image (if available)

The PDF is saved to the configured PDF_OUTPUT_DIR.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image as RLImage,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from config import PDF_OUTPUT_DIR

logger = logging.getLogger(__name__)

# Ensure output directory exists
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)


def generate_complaint_pdf(
    complaint_text: str,
    image_path: Optional[str] = None,
    severity: int = 1,
    output_filename: Optional[str] = None,
) -> Path:
    """
    Generate a formatted PDF complaint report.

    Parameters
    ----------
    complaint_text : str — the full complaint letter
    image_path : str, optional — path to the evidence image
    severity : int — 1, 2, or 3
    output_filename : str, optional — custom filename (auto-generated if None)

    Returns
    -------
    Path — absolute path to the generated PDF
    """
    if output_filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"complaint_{timestamp}.pdf"

    output_path = Path(PDF_OUTPUT_DIR) / output_filename
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # ── Header ────────────────────────────────────────────────
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Title"],
        fontSize=20,
        textColor=HexColor("#1a237e"),
        alignment=TA_CENTER,
        spaceAfter=10,
    )
    elements.append(Paragraph("🏙️ NagarDrishti", header_style))
    elements.append(Paragraph("AI-Powered Civic Complaint Report", styles["Heading3"]))
    elements.append(Spacer(1, 8 * mm))

    # ── Metadata Table ────────────────────────────────────────
    severity_labels = {1: "Level 1 — Safe", 2: "Level 2 — Risky", 3: "Level 3 — High Alert"}
    meta_data = [
        ["Date", datetime.now().strftime("%d %B %Y, %I:%M %p")],
        ["Severity", severity_labels.get(severity, "Unknown")],
        ["Report ID", output_filename.replace(".pdf", "")],
    ]
    meta_table = Table(meta_data, colWidths=[4 * cm, 12 * cm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), HexColor("#e8eaf6")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#9e9e9e")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10 * mm))

    # ── Complaint Body ────────────────────────────────────────
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontSize=11,
        leading=16,
        alignment=TA_LEFT,
    )
    for para in complaint_text.split("\n"):
        if para.strip():
            elements.append(Paragraph(para, body_style))
            elements.append(Spacer(1, 3 * mm))

    # ── Evidence Image ────────────────────────────────────────
    if image_path and Path(image_path).exists():
        elements.append(Spacer(1, 8 * mm))
        elements.append(Paragraph("📷 Evidence Image", styles["Heading4"]))
        elements.append(Spacer(1, 4 * mm))
        try:
            img = RLImage(image_path, width=14 * cm, height=10 * cm)
            img.hAlign = "CENTER"
            elements.append(img)
        except Exception as exc:
            logger.warning("Could not embed image: %s", exc)

    # ── Build PDF ─────────────────────────────────────────────
    doc.build(elements)
    logger.info("PDF generated: %s", output_path)
    return output_path.resolve()
