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
        self.model  = "gemini-2.5-flash"
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
            f"What is the official complaint/grievance email of the municipal corporation "
            f"or nagar palika for: '{payload.location_text}' in India?\n"
            f"Department: {payload.municipal_dept}\n"
            f"Reply with ONLY the email address. If unknown reply: grievance@municipalcorporation.gov.in"
        )
        try:
            resp  = self.client.models.generate_content(model=self.model, contents=prompt)
            email = resp.text.strip().lower()
            if "@" in email and "." in email:
                return email
        except Exception as e:
            print(f"[Legal] Email lookup failed: {e}")
        return "grievance@municipalcorporation.gov.in"

    # ── Reverse Geocode ───────────────────────────────────────────────────────
    def _reverse_geocode(self, lat: float, lon: float) -> str:
        """Asks Gemini to describe the location from GPS coords."""
        prompt = (
            f"Given GPS coordinates Latitude {lat}, Longitude {lon} in India, "
            f"give a short location name (area, city, state). "
            f"Reply with ONLY the location. Example: Near Bus Stand, Bikaner, Rajasthan"
        )
        try:
            resp = self.client.models.generate_content(model=self.model, contents=prompt)
            return resp.text.strip()
        except Exception:
            return f"GPS Location ({lat:.4f}, {lon:.4f})"

    # ── Legal Draft ───────────────────────────────────────────────────────────
    def _draft_complaint(self, payload) -> str:
        """
        Uses Gemini to write an official, legally-backed complaint letter.
        """
        deadline = DEADLINE_MAP.get(payload.severity_level, "within 7 days")

        prompt = f"""Write a formal Indian government complaint letter for road damage.

Complaint ID: {payload.complaint_id}
Date: {payload.timestamp[:10]}
Issue: {payload.issue_type} — Level {payload.severity_level} ({payload.severity_label})
Location: {payload.location_text}
Description: {payload.description}
Department: {payload.municipal_dept}
Deadline: {deadline}

Requirements:
1. Start with: To, The {payload.municipal_dept}, Municipal Authority
2. Add a Subject line mentioning severity level
3. Formal body describing the issue
4. Cite IPC Section 283, Motor Vehicles Act Section 138, and Municipal Corporation Act
5. Demand repair {deadline}
6. End with: Reported via NagarDrishti AI Civic Platform | Complaint ID: {payload.complaint_id}
7. Under 300 words, formal tone

Write ONLY the letter starting with To,"""

        try:
            resp = self.client.models.generate_content(model=self.model, contents=prompt)
            return resp.text.strip()
        except Exception as e:
            print(f"[Legal] Draft failed: {e}")
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
