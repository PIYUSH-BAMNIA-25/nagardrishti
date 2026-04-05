"""
NagarDrishti — Gateway Agent
agents/gateway_agent.py

The central orchestrator. Receives input from either:
    1. Vision Engine  (DetectionResult object with snapshot_b64)
    2. Citizen Portal (manual dict with image_path, description, location)

Then runs the full pipeline:
    Gateway → Veracity → Legal → Action

All sub-agents are called from here in sequence.
"""

import os
import sys
import base64
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google import genai
from google.genai import types
from config import GEMINI_API_KEY, REPORTS_DIR
from agents.gemini_client import call_with_fallback, TEXT_MODELS, VISION_MODELS

from agents.veracity_agent import VeracityAgent
from agents.legal_agent    import LegalAgent
from agents.action_agent   import ActionAgent





# ── Complaint Payload ─────────────────────────────────────────────────────────
class ComplaintPayload:
    """
    Unified complaint object passed between all agents.
    Built by Gateway, enriched by each subsequent agent.
    """
    def __init__(self):
        self.complaint_id    : str   = datetime.now().strftime("ND-%Y%m%d-%H%M%S")
        self.source          : str   = ""          # "vision" or "citizen"
        self.severity_level  : int   = 0           # 1 / 2 / 3
        self.severity_label  : str   = ""          # Safe / Risky / High Alert
        self.issue_type      : str   = ""          # pothole / crack / garbage / streetlight
        self.description     : str   = ""          # human-readable summary
        self.latitude        : float = 0.0
        self.longitude       : float = 0.0
        self.location_text   : str   = ""          # e.g. "Near Bus Stand, Bikaner"

        # EXIF GPS (extracted by Veracity Agent)
        self.exif_latitude   : float = 0.0
        self.exif_longitude  : float = 0.0
        self.image_b64       : str   = ""          # base64 JPEG for Gemini Vision
        self.image_path      : str   = ""          # local file path (if saved)
        self.timestamp       : str   = datetime.now().isoformat()

        # Filled by Veracity Agent
        self.is_verified     : bool  = False
        self.veracity_reason : str   = ""

        # Filled by Legal Agent
        self.legal_draft     : str   = ""
        self.municipal_email : str   = ""
        self.municipal_dept  : str   = ""

        # Filled by Action Agent
        self.pdf_path        : str   = ""
        self.email_sent      : bool  = False

    def to_dict(self) -> dict:
        return self.__dict__

    def summary(self) -> str:
        return (
            f"[{self.complaint_id}] {self.issue_type.upper()} | "
            f"Level {self.severity_level} {self.severity_label} | "
            f"{self.location_text}"
        )


# ── Gateway Agent ─────────────────────────────────────────────────────────────
class GatewayAgent:
    """
    Main orchestrator. Call process_vision() or process_citizen_report().
    """

    def __init__(self):
        self.client    = genai.Client(api_key=GEMINI_API_KEY)
        # No default model — uses fallback system per call
        self.veracity  = VeracityAgent()
        self.legal     = LegalAgent()
        self.action    = ActionAgent()
        os.makedirs(REPORTS_DIR, exist_ok=True)
        print("[Gateway] Agent ready ✓")

    # ── Entry Point 1: from Vision Engine ────────────────────────────────────
    def process_vision(self, detection_result) -> ComplaintPayload:
        """
        Called by detector.py when a Level 2/3 pothole is detected.

        Args:
            detection_result: DetectionResult object from vision/detector.py
        """
        print(f"\n[Gateway] 📡 Vision input received — Level {detection_result.severity_level}")

        payload = ComplaintPayload()
        payload.source         = "vision"
        payload.severity_level = detection_result.severity_level
        payload.severity_label = detection_result.severity_label
        payload.image_b64      = detection_result.snapshot_b64 or ""
        payload.issue_type     = (
            "pothole" if detection_result.pothole_count > 0 else "crack"
        )
        payload.latitude       = getattr(detection_result, 'latitude', 0.0)
        payload.longitude      = getattr(detection_result, 'longitude', 0.0)
        
        # Use camera_source as location hint if available
        # (set by detector.py real_agent_callback)
        if detection_result.camera_source and detection_result.camera_source != "[WEBCAM]":
            payload.location_text = detection_result.camera_source
        else:
            payload.location_text = "Location via Vision Engine"

        # Ask Gemini to generate a description from the detection data
        payload.description = self._generate_description(payload)

        # Save snapshot to disk for PDF attachment
        if payload.image_b64:
            payload.image_path = self._save_snapshot(payload)

        return self._run_pipeline(payload)

    # ── Entry Point 2: from Citizen Portal ───────────────────────────────────
    def process_citizen_report(
        self,
        image_path  : str,
        description : str,
        location    : str,
        issue_type  : str = "pothole",
        latitude    : float = 0.0,
        longitude   : float = 0.0,
    ) -> ComplaintPayload:
        """
        Called by the Streamlit frontend when a citizen submits a report.

        Args:
            image_path  : local path to uploaded image
            description : citizen's text description
            location    : human-readable location string
            issue_type  : pothole / crack / garbage / streetlight / other
            latitude    : GPS lat (optional, 0.0 if unknown)
            longitude   : GPS lng (optional, 0.0 if unknown)
        """
        print(f"\n[Gateway] 👤 Citizen report received — {issue_type} at {location}")

        payload = ComplaintPayload()
        payload.source        = "citizen"
        payload.issue_type    = issue_type
        payload.description   = description
        payload.location_text = location
        payload.latitude      = latitude
        payload.longitude     = longitude
        payload.image_path    = image_path

        # Encode image to base64 for Gemini Vision
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                payload.image_b64 = base64.b64encode(f.read()).decode("utf-8")

        # Assess severity from image using Gemini Vision
        payload.severity_level, payload.severity_label = self._assess_severity(payload)

        return self._run_pipeline(payload)

    # ── Pipeline Runner ───────────────────────────────────────────────────────
    def _run_pipeline(self, payload: ComplaintPayload) -> ComplaintPayload:
        """Runs Veracity → Legal → Action in sequence."""

        print(f"[Gateway] Running pipeline for: {payload.summary()}")

        # Step 1 — Veracity check
        print("[Gateway] → Step 1: Veracity check")
        payload = self.veracity.verify(payload)

        # Use EXIF GPS if available and user didn't provide GPS
        if payload.exif_latitude != 0.0 and payload.exif_longitude != 0.0:
            if payload.latitude == 0.0 or payload.longitude == 0.0:
                payload.latitude = payload.exif_latitude
                payload.longitude = payload.exif_longitude
                print(f"[Gateway] 📍 Using EXIF GPS: {payload.latitude:.6f}, {payload.longitude:.6f}")

        if not payload.is_verified:
            print(f"[Gateway] ❌ REJECTED — {payload.veracity_reason}")
            # Still generate PDF with REJECTED watermark (for demo/audit)
            print("[Gateway] → Generating REJECTED report PDF")
            payload = self.action.execute(payload)
            print(f"[Gateway] 📄 Rejected report saved: {payload.pdf_path}")
            return payload

        print(f"[Gateway] ✓ Verified — {payload.veracity_reason}")

        # Step 2 — Legal draft
        print("[Gateway] → Step 2: Legal draft")
        payload = self.legal.draft(payload)
        print(f"[Gateway] ✓ Legal draft ready — Dept: {payload.municipal_dept}")

        # Step 3 — Action (PDF + email)
        print("[Gateway] → Step 3: Action — PDF + Email")
        payload = self.action.execute(payload)

        if payload.email_sent:
            print(f"[Gateway] ✓ Email sent to {payload.municipal_email}")
        else:
            print(f"[Gateway] ⚠ Email not sent — PDF saved at {payload.pdf_path}")

        print(f"[Gateway] ✅ Pipeline complete — {payload.complaint_id}")
        return payload

    # ── Gemini Helpers ────────────────────────────────────────────────────────
    def _generate_description(self, payload) -> str:
        prompt = (
            f"A road issue was automatically detected by NagarDrishti AI.\n"
            f"Issue: {payload.issue_type}\n"
            f"Severity: Level {payload.severity_level} ({payload.severity_label})\n\n"
            f"Write a concise 2-sentence formal complaint description. "
            f"Be factual. Do not mention AI or cameras."
        )
        try:
            return call_with_fallback(
                self.client, prompt, TEXT_MODELS, "description"
            )
        except Exception as e:
            print(f"[Gateway] Description generation failed: {e}")
            return (
                f"A {payload.issue_type} at Level {payload.severity_level} "
                f"({payload.severity_label}) was detected. "
                f"Immediate inspection and repair is required."
            )

    def _assess_severity(self, payload) -> tuple:
        if not payload.image_b64:
            return 2, "Risky"
        prompt = (
            "Classify this road damage image severity as exactly one of:\n"
            "Level 1 Safe - minor cracks\n"
            "Level 2 Risky - pothole or moderate damage\n"
            "Level 3 High Alert - large pothole, severe damage\n\n"
            "Reply with ONLY: number and label. Example: 2 Risky"
        )
        try:
            import base64
            image_bytes = base64.b64decode(payload.image_b64)
            from google.genai import types
            contents = [
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            ]
            result = call_with_fallback(
                self.client, contents, VISION_MODELS, "severity assessment"
            )
            level = int(result[0]) if result and result[0].isdigit() else 2
            label = result[2:].strip() if len(result) > 2 else "Risky"
            return level, label
        except Exception as e:
            print(f"[Gateway] Severity assessment failed: {e}")
            return 2, "Risky"

    def _save_snapshot(self, payload: ComplaintPayload) -> str:
        """Saves base64 snapshot to disk and returns file path."""
        path = os.path.join(REPORTS_DIR, f"{payload.complaint_id}_snapshot.jpg")
        try:
            with open(path, "wb") as f:
                f.write(base64.b64decode(payload.image_b64))
        except Exception as e:
            print(f"[Gateway] Snapshot save failed: {e}")
        return path


# ── Quick Test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Simulate a citizen report (no vision engine needed)
    gateway = GatewayAgent()
    result  = gateway.process_citizen_report(
        image_path  = "assets/sample_pothole.jpg",
        description = "Large pothole on main road causing vehicle damage",
        location    = "Near Gandhi Chowk, Bikaner, Rajasthan",
        issue_type  = "pothole",
        latitude    = 28.0229,
        longitude   = 73.3119,
    )
    print("\n── Final Payload ──────────────────────────────")
    print(f"Complaint ID   : {result.complaint_id}")
    print(f"Verified       : {result.is_verified}")
    print(f"Legal Draft    : {result.legal_draft[:100]}...")
    print(f"PDF Path       : {result.pdf_path}")
    print(f"Email Sent     : {result.email_sent}")
