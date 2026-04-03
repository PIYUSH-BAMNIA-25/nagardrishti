"""
NagarDrishti — Action Agent (v2)
agents/action_agent.py

Final stage of the pipeline. Responsible for:
    1. Generating a formatted PDF complaint report (ReportLab)
       — Supports both VERIFIED and REJECTED reports
       — REJECTED reports get a big red watermark overlay
    2. Sending the complaint email to the municipal department
       with the PDF and snapshot image as attachments
       — Only sends email for VERIFIED complaints

Fills in:
    payload.pdf_path
    payload.email_sent
"""

import os
import smtplib
import base64
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.base      import MIMEBase
from email                import encoders
from datetime             import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles    import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units     import cm, mm
from reportlab.lib           import colors
from reportlab.platypus      import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, HRFlowable, PageBreak
)
from reportlab.lib.enums  import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen      import canvas as pdfcanvas

from config import (
    REPORTS_DIR, SMTP_HOST, SMTP_PORT,
    SMTP_USER, SMTP_PASS, SENDER_EMAIL, SENDER_NAME
)


# ── Color Palette ─────────────────────────────────────────────────────────────
NAVY       = colors.HexColor("#1A237E")
DARK_TEXT   = colors.HexColor("#212121")
GREY_TEXT   = colors.HexColor("#616161")
LIGHT_BG   = colors.HexColor("#F8F9FA")
BORDER     = colors.HexColor("#DEE2E6")
WHITE      = colors.white
GREEN      = colors.HexColor("#2E7D32")
ORANGE     = colors.HexColor("#E65100")
RED        = colors.HexColor("#C62828")
REJECT_RED = colors.HexColor("#D32F2F")

SEVERITY_COLORS = {1: GREEN, 2: ORANGE, 3: RED}

# ── Page width for content ────────────────────────────────────────────────────
PAGE_W = A4[0] - 4 * cm   # usable width = A4 - margins


class ActionAgent:

    def __init__(self):
        os.makedirs(REPORTS_DIR, exist_ok=True)
        print("[Action] Agent ready ✓")

    def execute(self, payload) -> object:
        """
        Main entry. Generates PDF then sends email (only if verified).
        Returns enriched payload.
        """
        # Step 1: Generate PDF (always — even for rejected)
        payload.pdf_path = self._generate_pdf(payload)
        print(f"[Action] PDF generated: {payload.pdf_path}")

        # Step 2: Send Email (only for verified complaints)
        if payload.is_verified:
            payload.email_sent = self._send_email(payload)
        else:
            print("[Action] Complaint rejected — skipping email")
            payload.email_sent = False

        return payload

    # ── PDF Generator ─────────────────────────────────────────────────────────
    def _generate_pdf(self, payload) -> str:
        """Creates a clean, professional complaint PDF."""

        is_rejected = not payload.is_verified
        suffix      = "REJECTED" if is_rejected else "report"
        pdf_path    = os.path.join(REPORTS_DIR, f"{payload.complaint_id}_{suffix}.pdf")

        # Build doc with watermark callback for rejected reports
        doc = SimpleDocTemplate(
            pdf_path, pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm
        )

        story  = []
        styles = self._build_styles()

        # ── Title Block ──────────────────────────────────────────────────────
        story.append(Paragraph("NAGARDRISHTI", styles["title"]))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph("AI-Powered Civic Complaint System", styles["subtitle"]))
        story.append(Spacer(1, 4*mm))

        # Divider line
        story.append(HRFlowable(
            width="100%", thickness=2, color=NAVY,
            spaceAfter=4*mm, spaceBefore=0
        ))

        # ── Status Banner ────────────────────────────────────────────────────
        if is_rejected:
            banner_color = REJECT_RED
            banner_text  = "⊘  COMPLAINT REJECTED — FAILED VERIFICATION  ⊘"
        else:
            sev_color    = SEVERITY_COLORS.get(payload.severity_level, ORANGE)
            banner_color = sev_color
            banner_text  = f"LEVEL {payload.severity_level}  —  {payload.severity_label.upper()}"

        banner = Table(
            [[Paragraph(banner_text, styles["banner_text"])]],
            colWidths=[PAGE_W]
        )
        banner.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), banner_color),
            ("ALIGN",         (0,0), (-1,-1), "CENTER"),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ]))
        story.append(banner)
        story.append(Spacer(1, 5*mm))

        # ── Complaint Details ────────────────────────────────────────────────
        story.append(Paragraph("Complaint Details", styles["section"]))
        story.append(Spacer(1, 2*mm))

        label_w = 4.5 * cm
        value_w = PAGE_W - label_w

        details = [
            ["Complaint ID",  payload.complaint_id],
            ["Date & Time",   payload.timestamp[:19].replace("T", "  ")],
            ["Source",         payload.source.title()],
            ["Issue Type",     payload.issue_type.title()],
            ["Severity",       f"Level {payload.severity_level} — {payload.severity_label}"],
            ["Location",       payload.location_text or "Not specified"],
        ]
        if payload.latitude:
            details.append(["GPS Coordinates", f"{payload.latitude:.4f}, {payload.longitude:.4f}"])
        if payload.municipal_dept:
            details.append(["Department", payload.municipal_dept])

        # Wrap long values in Paragraphs to prevent overlap
        formatted = []
        for label, value in details:
            formatted.append([
                Paragraph(f"<b>{label}</b>", styles["table_label"]),
                Paragraph(str(value), styles["table_value"]),
            ])

        det_table = Table(formatted, colWidths=[label_w, value_w])
        det_table.setStyle(TableStyle([
            ("VALIGN",         (0,0), (-1,-1), "TOP"),
            ("TOPPADDING",     (0,0), (-1,-1), 5),
            ("BOTTOMPADDING",  (0,0), (-1,-1), 5),
            ("LEFTPADDING",    (0,0), (-1,-1), 8),
            ("RIGHTPADDING",   (0,0), (-1,-1), 8),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [WHITE, LIGHT_BG]),
            ("LINEBELOW",      (0,0), (-1,-1), 0.5, BORDER),
        ]))
        story.append(det_table)
        story.append(Spacer(1, 5*mm))

        # ── Verification Status ──────────────────────────────────────────────
        story.append(Paragraph("Verification Status", styles["section"]))
        story.append(Spacer(1, 2*mm))

        # Parse veracity reason into readable lines
        reason_parts = payload.veracity_reason.split(" | ")
        for part in reason_parts:
            # Truncate very long reasons
            if len(part) > 120:
                part = part[:117] + "..."
            color = "#2E7D32" if "VERIFIED" in part or "PASS" in part or "+30" in part or "+20" in part else (
                "#C62828" if "REJECT" in part or "-" in part[:15] else "#424242"
            )
            story.append(Paragraph(
                f'<font color="{color}">• {part}</font>',
                styles["body"]
            ))
        story.append(Spacer(1, 3*mm))

        # ── Description ──────────────────────────────────────────────────────
        if payload.description:
            story.append(Paragraph("Issue Description", styles["section"]))
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(payload.description, styles["body"]))
            story.append(Spacer(1, 4*mm))

        # ── Photo Evidence ───────────────────────────────────────────────────
        if payload.image_path and os.path.exists(payload.image_path):
            story.append(Paragraph("Photo Evidence", styles["section"]))
            story.append(Spacer(1, 2*mm))
            try:
                img = RLImage(payload.image_path, width=13*cm, height=8*cm,
                              kind='proportional')
                story.append(img)
            except Exception as e:
                story.append(Paragraph(f"[Image could not be embedded: {e}]", styles["body"]))
            story.append(Spacer(1, 4*mm))

        # ── Legal Draft (only for verified) ──────────────────────────────────
        if payload.is_verified and payload.legal_draft:
            story.append(Paragraph("Official Complaint Letter", styles["section"]))
            story.append(Spacer(1, 2*mm))
            for line in payload.legal_draft.split("\n"):
                line = line.strip()
                if line:
                    # Escape any XML special chars for ReportLab
                    safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    story.append(Paragraph(safe, styles["body"]))
            story.append(Spacer(1, 4*mm))
        elif is_rejected:
            story.append(Paragraph("Official Complaint Letter", styles["section"]))
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(
                '<font color="#C62828"><b>Not generated — complaint failed verification.</b></font>',
                styles["body"]
            ))
            story.append(Spacer(1, 4*mm))

        # ── Footer ───────────────────────────────────────────────────────────
        story.append(HRFlowable(
            width="100%", thickness=1, color=BORDER,
            spaceAfter=3*mm, spaceBefore=2*mm
        ))
        story.append(Paragraph(
            f"Generated by NagarDrishti AI Civic Platform  •  {payload.complaint_id}  •  "
            f"{datetime.now().strftime('%d %b %Y, %H:%M')}",
            styles["footer"]
        ))

        # Build with optional REJECTED watermark
        if is_rejected:
            doc.build(story, onFirstPage=self._rejected_watermark,
                      onLaterPages=self._rejected_watermark)
        else:
            doc.build(story)

        return pdf_path

    # ── REJECTED Watermark ────────────────────────────────────────────────────
    @staticmethod
    def _rejected_watermark(canvas_obj, doc):
        """Draws a large diagonal REJECTED watermark on the page."""
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica-Bold", 72)
        canvas_obj.setFillColor(colors.Color(0.85, 0.15, 0.15, alpha=0.15))
        canvas_obj.translate(A4[0] / 2, A4[1] / 2)
        canvas_obj.rotate(45)
        canvas_obj.drawCentredString(0, 0, "REJECTED")
        canvas_obj.restoreState()

        # Also draw a red border
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(colors.Color(0.85, 0.15, 0.15, alpha=0.3))
        canvas_obj.setLineWidth(3)
        canvas_obj.rect(1.5*cm, 1.5*cm, A4[0] - 3*cm, A4[1] - 3*cm, stroke=1, fill=0)
        canvas_obj.restoreState()

    # ── Styles ────────────────────────────────────────────────────────────────
    @staticmethod
    def _build_styles() -> dict:
        """Builds all paragraph styles used in the PDF."""
        return {
            "title": ParagraphStyle(
                "title", fontSize=22, fontName="Helvetica-Bold",
                textColor=NAVY, alignment=TA_CENTER, spaceAfter=0,
                leading=26
            ),
            "subtitle": ParagraphStyle(
                "subtitle", fontSize=10, fontName="Helvetica",
                textColor=GREY_TEXT, alignment=TA_CENTER, spaceAfter=0,
                leading=14
            ),
            "section": ParagraphStyle(
                "section", fontSize=12, fontName="Helvetica-Bold",
                textColor=NAVY, spaceAfter=0, spaceBefore=4,
                borderPadding=0,
            ),
            "body": ParagraphStyle(
                "body", fontSize=9.5, fontName="Helvetica",
                textColor=DARK_TEXT, leading=15, spaceAfter=4,
                wordWrap="CJK",    # helps with long words
            ),
            "table_label": ParagraphStyle(
                "tbl_label", fontSize=9.5, fontName="Helvetica-Bold",
                textColor=NAVY, leading=13,
            ),
            "table_value": ParagraphStyle(
                "tbl_value", fontSize=9.5, fontName="Helvetica",
                textColor=DARK_TEXT, leading=13,
                wordWrap="CJK",
            ),
            "banner_text": ParagraphStyle(
                "banner", fontSize=13, fontName="Helvetica-Bold",
                textColor=WHITE, alignment=TA_CENTER,
            ),
            "footer": ParagraphStyle(
                "footer", fontSize=7.5, fontName="Helvetica",
                textColor=GREY_TEXT, alignment=TA_CENTER,
            ),
        }

    # ── Email Sender ──────────────────────────────────────────────────────────
    def _send_email(self, payload) -> bool:
        """
        Sends the complaint email with PDF + image attachments.
        Returns True if sent successfully.
        """
        if not SMTP_USER or not SMTP_PASS:
            print("[Action] SMTP credentials not configured in .env — skipping email")
            return False

        try:
            msg = MIMEMultipart("mixed")
            msg["From"]    = f"{SENDER_NAME} <{SENDER_EMAIL}>"
            msg["To"]      = payload.municipal_email
            msg["Subject"] = (
                f"[NagarDrishti] LEVEL {payload.severity_level} Road Damage Complaint — "
                f"{payload.location_text} | {payload.complaint_id}"
            )

            # Email body
            body = MIMEText(payload.legal_draft, "plain")
            msg.attach(body)

            # Attach PDF
            if payload.pdf_path and os.path.exists(payload.pdf_path):
                with open(payload.pdf_path, "rb") as f:
                    pdf_part = MIMEBase("application", "octet-stream")
                    pdf_part.set_payload(f.read())
                encoders.encode_base64(pdf_part)
                pdf_part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={os.path.basename(payload.pdf_path)}"
                )
                msg.attach(pdf_part)

            # Attach snapshot image
            if payload.image_path and os.path.exists(payload.image_path):
                with open(payload.image_path, "rb") as f:
                    img_part = MIMEBase("image", "jpeg")
                    img_part.set_payload(f.read())
                encoders.encode_base64(img_part)
                img_part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={payload.complaint_id}_evidence.jpg"
                )
                msg.attach(img_part)

            # Send via SMTP TLS
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SENDER_EMAIL, payload.municipal_email, msg.as_string())

            print(f"[Action] ✓ Email sent to {payload.municipal_email}")
            return True

        except Exception as e:
            print(f"[Action] Email failed: {e}")
            return False
