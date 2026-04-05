"""
NagarDrishti — Central Config
config.py

Loads all environment variables via python-dotenv.
Import from this file everywhere else — never import os.getenv directly.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent / ".env")

# ── Gemini API ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ── Supabase ───────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ── Email / SMTP ───────────────────────────────────────────────────────────────
SMTP_HOST    = os.getenv("SMTP_HOST",    "smtp.gmail.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER",    "")
SMTP_PASS    = os.getenv("SMTP_PASS",    "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", SMTP_USER)
SENDER_NAME  = os.getenv("SENDER_NAME",  "NagarDrishti AI System")

# ── Storage Paths ──────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
REPORTS_DIR = str(BASE_DIR / "reports")   # PDFs + snapshots saved here

# ── Known Municipal Emails ─────────────────────────────────────────────────────
# Add your city here. Gateway Agent checks this before asking Gemini.
MUNICIPAL_EMAILS = {
    "bikaner"   : "tailaung16@gmail.com",
    "jaipur"    : "tailaung16@gmail.com",
    "jodhpur"   : "tailaung16@gmail.com",
    "delhi"     : "tailaung16@gmail.com",
    "mumbai"    : "tailaung16@gmail.com",
    "bangalore" : "tailaung16@gmail.com",
    "hyderabad" : "tailaung16@gmail.com",
    "chennai"   : "tailaung16@gmail.com",
}

# ── Testing / App ──────────────────────────────────────────────────────────────
TEST_EMAIL_OVERRIDE = os.getenv("TEST_EMAIL_OVERRIDE", "tailaung16@gmail.com")
APP_TITLE           = os.getenv("APP_TITLE", "NagarDrishti")
