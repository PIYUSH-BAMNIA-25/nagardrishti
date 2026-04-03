"""
email_sender.py — Complaint Email Dispatch Utility

Sends the generated complaint (plain text + PDF attachment) to the
relevant municipal department via SMTP.

Configuration is loaded from environment variables via config.py:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, DEFAULT_RECIPIENT
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD

logger = logging.getLogger(__name__)


def send_complaint_email(
    recipient: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None,
) -> bool:
    """
    Send a complaint email with an optional PDF attachment.

    Parameters
    ----------
    recipient : str — target email address
    subject : str — email subject line
    body : str — plain-text email body (complaint letter)
    attachment_path : str, optional — path to PDF report to attach

    Returns
    -------
    bool — True if email was sent successfully
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.error("SMTP credentials not configured — cannot send email.")
        return False

    # Build the message
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # Attach PDF if provided
    if attachment_path:
        pdf_path = Path(attachment_path)
        if pdf_path.exists():
            try:
                with open(pdf_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={pdf_path.name}",
                    )
                    msg.attach(part)
            except Exception as exc:
                logger.warning("Failed to attach PDF: %s", exc)
        else:
            logger.warning("Attachment file not found: %s", pdf_path)

    # Send via SMTP
    # TODO: Add retry logic and connection pooling for production
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, recipient, msg.as_string())
        logger.info("Email sent to %s ✓", recipient)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed — check SMTP_USER / SMTP_PASSWORD.")
        return False
    except smtplib.SMTPException as exc:
        logger.error("SMTP error: %s", exc)
        return False
    except Exception as exc:
        logger.error("Unexpected email error: %s", exc)
        return False
