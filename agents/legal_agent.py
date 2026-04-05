"""
NagarDrishti — Legal Agent
agents/legal_agent.py

Responsibilities:
    1. Identifies the correct municipal department based on issue type
    2. Finds the municipal email address for the given location
    3. Drafts an official, legally-backed complaint citing:
       - IPC Section 283 (public danger)
       - Motor Vehicles Act Section 138
       - Municipal Corporation Act (maintenance obligations)
    4. Sets a repair deadline based on severity

Fills in:
    payload.legal_draft
    payload.municipal_email
    payload.municipal_dept
    payload.location_text (enriched if only GPS was given)
"""

import json
from google import genai
from config import GEMINI_API_KEY, MUNICIPAL_EMAILS
from agents.gemini_client import call_with_fallback, TEXT_MODELS


# ── Department Routing ────────────────────────────────────────────────────────
ISSUE_DEPT_MAP = {
    "pothole"    : "Roads & Infrastructure Department",
    "crack"      : "Roads & Infrastructure Department",
    "garbage"    : "Sanitation & Solid Waste Management",
    "streetlight": "Electrical & Street Lighting Department",
    "drain"      : "Drainage & Sewerage Department",
    "other"      : "Public Works Department",
}

# Severity → repair deadline
DEADLINE_MAP = {
    1: "within 30 days",
    2: "within 7 days",
    3: "within 48 hours",
}


class LegalAgent:

    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        # Uses fallback system — no single model
        print("[Legal] Agent ready ✓")

    def draft(self, payload) -> object:
        """
        Main entry. Fills legal_draft, municipal_email, municipal_dept.
        Returns enriched payload.
        """

        # Resolve department
        payload.municipal_dept = ISSUE_DEPT_MAP.get(
            payload.issue_type, "Public Works Department"
        )

        # Resolve location text if only GPS given
        if not payload.location_text and payload.latitude:
            payload.location_text = self._reverse_geocode(
                payload.latitude, payload.longitude
            )

        # Resolve municipal email
        payload.municipal_email = self._find_municipal_email(payload)

        # Draft the complaint
        payload.legal_draft = self._draft_complaint(payload)

        return payload

    # ── Email Resolver ────────────────────────────────────────────────────────
    def _find_municipal_email(self, payload) -> str:
        """
        Looks up municipal email from config first.
        Falls back to Gemini if not found.
        """
        location_lower = payload.location_text.lower()
        for city, email in MUNICIPAL_EMAILS.items():
            if city.lower() in location_lower:
                return email
        prompt = (
            f"Official grievance email for municipal corporation "
            f"in '{payload.location_text}', India. "
            f"Department: {payload.municipal_dept}. "
            f"Reply with ONLY the email. If unknown: grievance@municipalcorporation.gov.in"
        )
        try:
            email = call_with_fallback(
                self.client, prompt, TEXT_MODELS, "email lookup"
            ).lower()
            if "@" in email and "." in email:
                return email
        except Exception as e:
            print(f"[Legal] Email lookup failed: {e}")
        
        from config import TEST_EMAIL_OVERRIDE
        return TEST_EMAIL_OVERRIDE or "grievance@municipalcorporation.gov.in"

    # ── Reverse Geocode ───────────────────────────────────────────────────────
    def _reverse_geocode(self, lat: float, lon: float) -> str:
        """Asks Gemini to describe the location from GPS coords."""
        prompt = (
            f"GPS: Lat {lat}, Lon {lon} in India. "
            f"Short location name only. "
            f"Example: Near Bus Stand, Bikaner, Rajasthan"
        )
        try:
            return call_with_fallback(
                self.client, prompt, TEXT_MODELS, "geocode"
            )
        except Exception:
            return f"GPS ({lat:.4f}, {lon:.4f})"

    # ── Legal Draft ───────────────────────────────────────────────────────────
    def _draft_complaint(self, payload) -> str:
        """
        Uses Gemini to write an official, legally-backed complaint letter.
        """
        deadline = DEADLINE_MAP.get(payload.severity_level, "within 7 days")
        lat = getattr(payload, 'latitude', 0.0) or 0.0
        lon = getattr(payload, 'longitude', 0.0) or 0.0

        prompt = f"""You are a legal complaint drafting system for 
Indian municipal governance. Write a formal complaint letter.

COMPLAINT DETAILS:
- ID: {payload.complaint_id}
- Date: {payload.timestamp[:10]}
- Issue Type: {payload.issue_type}
- Severity: Level {payload.severity_level} — {payload.severity_label}
- Location: {payload.location_text}
- GPS: {lat:.4f}N, {lon:.4f}E
- Description: {payload.description}
- Department: {payload.municipal_dept}
- Repair Deadline: {deadline}
- Source: {'Autonomous AI Vision System' if getattr(payload, 'source', '') == 'vision' else 'Citizen Report'}

MANDATORY REQUIREMENTS:
1. Address: To, The {payload.municipal_dept}, {payload.location_text.split(',')[-1].strip() if payload.location_text else 'Municipal Authority'}
2. Subject line must mention: Level {payload.severity_level}, issue type, location
3. Opening paragraph describing the {payload.issue_type} at {payload.location_text}
4. Cite these exact laws:
   - IPC Section 283 (danger or obstruction in public way)
   - Motor Vehicles Act Section 138 (power to make rules regarding roads)  
   - Municipal Corporations Act obligation for road maintenance
5. State the severity level and its implications for public safety
6. Demand repair {deadline} due to Level {payload.severity_level} classification
7. Mention GPS coordinates: {lat:.4f}N, {lon:.4f}E
8. If from vision engine, mention: "Detected by NagarDrishti AI Vision System"
9. Closing: "Reported via NagarDrishti AI Civic Platform | ID: {payload.complaint_id}"
10. Keep under 350 words, formal government tone"""

        try:
            return call_with_fallback(
                self.client, prompt, TEXT_MODELS, "legal draft"
            )
        except Exception as e:
            print(f"[Legal] All models failed: {e}")
            return self._fallback_draft(payload, deadline)

    def _fallback_draft(self, payload, deadline: str) -> str:
        """Fallback template when Gemini is unavailable."""
        return f"""To,
The {payload.municipal_dept},
Municipal Authority

Subject: Urgent Complaint — Level {payload.severity_level} Road Damage ({payload.severity_label}) at {payload.location_text}

Sir/Madam,

I hereby bring to your notice a serious road damage issue detected at {payload.location_text} on {payload.timestamp[:10]}.

Nature of Issue: {payload.issue_type.title()}
Severity: Level {payload.severity_level} — {payload.severity_label}
Description: {payload.description}

Under IPC Section 283 (obstruction in public way) and the Motor Vehicles Act Section 138, the concerned authority is legally obligated to maintain safe road conditions. This damage poses an immediate risk to public safety.

You are hereby requested to take corrective action {deadline}.

Reported via NagarDrishti AI Civic Platform | Complaint ID: {payload.complaint_id}"""
