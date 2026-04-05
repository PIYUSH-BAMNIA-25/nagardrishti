"""
NagarDrishti — Veracity Agent (v2)
agents/veracity_agent.py

Three-stage fake photo detection with TRUST SCORING:

    Stage 1 — EXIF metadata check (fast, free)
              • Has GPS? → +30 trust   (GPS matches location → +40)
              • Has timestamp? → +15 trust
              • No EXIF at all? → -25 trust (AI/screenshots have no EXIF)

    Stage 2 — AI-Generated Image Detection (Gemini Vision)
              • Specifically asks: "Is this AI-generated?"
              • Checks for: unnatural textures, perfect symmetry, weird
                artifacts, missing imperfections, too-clean edges
              • AI-generated → -40 trust
              • Real photo   → +30 trust

    Stage 3 — Authenticity Check (Gemini Vision)
              • Is this a stock photo, watermarked, or irrelevant?
              • Stock/fake  → -30 trust
              • Real street → +20 trust

Trust Score Thresholds:
    >= 30  → VERIFIED
    0-29   → SUSPICIOUS (verified with warning)
    < 0    → REJECTED

Result:
    payload.is_verified     = True / False
    payload.veracity_reason = human-readable explanation with score
"""

import io
import math
import json
import base64
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from google import genai
from google.genai import types
from config import GEMINI_API_KEY
from agents.gemini_client import call_with_fallback, VISION_MODELS


class VeracityAgent:

    TRUST_THRESHOLD_PASS = 30       # >= 30 = verified
    TRUST_THRESHOLD_SUSPICIOUS = 0  # 0-29  = suspicious but allowed
    # < 0 = rejected

    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        # Uses fallback system — no single model
        print("[Veracity] Agent ready ✓")

    def verify(self, payload) -> object:
        """
        Main entry point. Runs all stages, computes trust score.
        Sets payload.is_verified and payload.veracity_reason.
        """

        # Vision engine captures are auto-trusted (webcam = live)
        if payload.source == "vision":
            payload.is_verified     = True
            payload.veracity_reason = "Live camera capture — auto-verified (trust: 100)"
            return payload

        trust_score = 0
        reasons     = []

        # ── Stage 1: EXIF Metadata ───────────────────────────────────────────
        exif_score, exif_reason = self._check_exif(payload)
        trust_score += exif_score
        reasons.append(f"EXIF({exif_score:+d}): {exif_reason}")
        print(f"[Veracity] Stage 1 EXIF — score: {exif_score:+d} | {exif_reason}")

        # ── Stage 2: AI-Generation Detection ─────────────────────────────────
        if payload.image_b64:
            ai_score, ai_reason = self._check_ai_generated(payload)
            trust_score += ai_score
            reasons.append(f"AI-Check({ai_score:+d}): {ai_reason}")
            print(f"[Veracity] Stage 2 AI Detection — score: {ai_score:+d} | {ai_reason}")

            # ── Stage 3: Stock/Fake Check ────────────────────────────────────
            stock_score, stock_reason = self._check_stock_fake(payload)
            trust_score += stock_score
            reasons.append(f"Stock({stock_score:+d}): {stock_reason}")
            print(f"[Veracity] Stage 3 Stock Check — score: {stock_score:+d} | {stock_reason}")
        else:
            reasons.append("No image — skipped vision checks")

        # ── Stage 4: Cross-Validation ────────────────────────────────────────
        # If EXIF says "no metadata" but Gemini says "real photo" → contradiction
        # Real phone photos ALWAYS have EXIF. AI images never do.
        if exif_score <= -20 and trust_score > 0:
            # Gemini was fooled — the image looks real but has no EXIF
            cross_penalty = -30
            trust_score += cross_penalty
            cross_reason = "No EXIF but 'looks real' = contradiction (real phones embed EXIF)"
            reasons.append(f"Cross-Check({cross_penalty:+d}): {cross_reason}")
            print(f"[Veracity] Stage 4 Cross-Validation — penalty: {cross_penalty:+d} | {cross_reason}")

        # ── Final Decision ───────────────────────────────────────────────────
        reason_str = " | ".join(reasons)

        if trust_score >= self.TRUST_THRESHOLD_PASS:
            payload.is_verified     = True
            payload.veracity_reason = f"VERIFIED (trust: {trust_score}) — {reason_str}"
        elif trust_score >= self.TRUST_THRESHOLD_SUSPICIOUS:
            payload.is_verified     = True
            payload.veracity_reason = f"SUSPICIOUS but allowed (trust: {trust_score}) — {reason_str}"
        else:
            payload.is_verified     = False
            payload.veracity_reason = f"REJECTED (trust: {trust_score}) — {reason_str}"

        print(f"[Veracity] Final trust score: {trust_score} → {'✓ PASS' if payload.is_verified else '✗ REJECT'}")
        return payload

    # ── Stage 1: EXIF Metadata ────────────────────────────────────────────────
    def _check_exif(self, payload) -> tuple:
        """
        Extracts EXIF metadata. Returns (score_delta, reason).
        No EXIF = negative score (AI images never have EXIF).
        """
        if not payload.image_b64:
            return -10, "No image provided"

        try:
            img_bytes = base64.b64decode(payload.image_b64)
            img       = Image.open(io.BytesIO(img_bytes))
            exif_raw  = img._getexif()

            if not exif_raw:
                return -25, "No EXIF metadata (likely AI-generated, screenshot, or download)"

            exif = {TAGS.get(k, k): v for k, v in exif_raw.items()}
            score  = 10  # Has EXIF = small positive
            detail = "EXIF present"

            # Check for GPS data
            gps_info = exif.get("GPSInfo")
            if gps_info:
                gps = {GPSTAGS.get(k, k): v for k, v in gps_info.items()}
                lat = self._gps_to_decimal(
                    gps.get("GPSLatitude"), gps.get("GPSLatitudeRef", "N")
                )
                lon = self._gps_to_decimal(
                    gps.get("GPSLongitude"), gps.get("GPSLongitudeRef", "E")
                )

                if lat and lon and payload.latitude and payload.longitude:
                    dist = self._haversine(lat, lon, payload.latitude, payload.longitude)
                    if dist > 50:
                        return -40, f"GPS mismatch — photo taken {dist:.0f}km from reported location"
                    score += 30
                    detail = f"GPS verified — {dist:.1f}km from location"
                else:
                    score += 15
                    detail = "GPS data found in image"

            # Check for timestamp
            dt = exif.get("DateTimeOriginal") or exif.get("DateTime")
            if dt:
                score += 15
                detail += f", timestamp: {dt}"

            # Check for camera make/model (real cameras embed this)
            make  = exif.get("Make", "")
            model = exif.get("Model", "")
            if make or model:
                score += 10
                detail += f", camera: {make} {model}".strip()

            return score, detail

        except Exception as e:
            return -5, f"EXIF read error: {str(e)[:60]}"

    # ── Stage 2: AI-Generated Detection ───────────────────────────────────────
    def _check_ai_generated(self, payload) -> tuple:
        """
        Uses Gemini to specifically detect AI-generated images.
        Returns (score_delta, reason).
        """
        prompt = """You are an AI-generated image detector. Analyze this image carefully.

Look for these AI-generation artifacts:
1. TEXTURES: Too smooth, plastic-like surfaces, or repetitive patterns
2. EDGES: Unnaturally clean or blurry transitions between objects
3. LIGHTING: Inconsistent shadows, light sources that don't match
4. DETAILS: Distorted text, warped signs, impossible geometry
5. PERFECTION: Too perfect/clean for a real street photo — real roads have random debris, dirt, imperfections
6. CONTEXT: Missing natural context clues (no real pedestrians, vehicles look odd, buildings distorted)
7. DEPTH: Unnatural depth of field, background inconsistencies

Answer ONLY in this exact JSON format:
{
  "is_ai_generated": true or false,
  "confidence": 0-100,
  "artifacts_found": ["list of specific artifacts you noticed"],
  "reason": "one sentence explanation"
}"""

        try:
            import base64
            from google.genai import types
            image_bytes = base64.b64decode(payload.image_b64)
            contents = [
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            ]
            text = call_with_fallback(
                self.client, contents, VISION_MODELS, "ai detection"
            )
            result = self._parse_json(text)

            is_ai      = result.get("is_ai_generated", False)
            confidence = result.get("confidence", 50)
            reason     = result.get("reason", "")
            artifacts  = result.get("artifacts_found", [])

            if is_ai and confidence >= 60:
                artifact_list = ", ".join(artifacts[:3]) if artifacts else "general AI artifacts"
                return -40, f"AI-generated ({confidence}%): {reason}. Found: {artifact_list}"
            elif is_ai and confidence >= 40:
                return -15, f"Possibly AI-generated ({confidence}%): {reason}"
            else:
                return 30, f"Appears real ({confidence}% confident): {reason}"

        except Exception as e:
            print(f"[Veracity] AI detection failed: {e}")
            return 0, "AI detection inconclusive"

    # ── Stage 3: Stock/Fake Check ─────────────────────────────────────────────
    def _check_stock_fake(self, payload) -> tuple:
        """
        Checks if the image is a stock photo, watermarked, or irrelevant.
        Returns (score_delta, reason).
        """
        prompt = """Analyze this image for authenticity. Answer ONLY in JSON:
{
  "verdict": "REAL_STREET_PHOTO" or "STOCK_PHOTO" or "IRRELEVANT",
  "confidence": 0-100,
  "reason": "one sentence"
}

STOCK_PHOTO = professional lighting, watermarks, logos, staged setup, too polished
IRRELEVANT = not a road/infrastructure image at all (random selfie, food photo, etc.)
REAL_STREET_PHOTO = candid photo of actual road/street showing real damage or infrastructure"""

        try:
            import base64
            from google.genai import types
            image_bytes = base64.b64decode(payload.image_b64)
            contents = [
                prompt,
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            ]
            text = call_with_fallback(
                self.client, contents, VISION_MODELS, "stock photo check"
            )
            result = self._parse_json(text)

            verdict    = result.get("verdict", "REAL_STREET_PHOTO")
            confidence = result.get("confidence", 50)
            reason     = result.get("reason", "")

            if verdict == "IRRELEVANT" and confidence >= 60:
                return -35, f"Not a road/infrastructure image ({confidence}%): {reason}"
            elif verdict == "STOCK_PHOTO" and confidence >= 60:
                return -30, f"Stock/staged photo ({confidence}%): {reason}"
            elif verdict == "REAL_STREET_PHOTO":
                return 20, f"Real street photo ({confidence}%): {reason}"
            else:
                return 5, f"Unclear ({confidence}%): {reason}"

        except Exception as e:
            print(f"[Veracity] Stock check failed: {e}")
            return 0, "Stock check inconclusive"

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _parse_json(self, text: str) -> dict:
        """Safely parses JSON from Gemini response, handling markdown fences."""
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())

    def _gps_to_decimal(self, dms, ref) -> float | None:
        """Converts DMS GPS tuple to decimal degrees."""
        try:
            d, m, s = dms
            decimal = float(d) + float(m) / 60 + float(s) / 3600
            if ref in ("S", "W"):
                decimal = -decimal
            return decimal
        except Exception:
            return None

    def _haversine(self, lat1, lon1, lat2, lon2) -> float:
        """Returns distance in km between two GPS coordinates."""
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) *
             math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
