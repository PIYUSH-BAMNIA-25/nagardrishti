# 🏙️ NagarDrishti — AI-Powered Civic Complaint Automation

**NagarDrishti** (नगर दृष्टि — "City Vision") is an AI-powered system that automates civic complaint registration for issues like potholes, garbage, and broken streetlights. It uses computer vision (YOLOv8), Google Gemini AI, and multi-agent orchestration to detect, verify, escalate, and report infrastructure problems to municipal authorities.

---

## ✨ Features

| Module | Description |
|--------|-------------|
| **AI Detection** | YOLOv8-based pothole detection with 3-level severity classification |
| **Photo Verification** | EXIF + Gemini Vision analysis to detect fake/stock images |
| **Legal Drafting** | Auto-generates legally-backed complaints citing the Road Safety Act |
| **PDF Reports** | Professional complaint PDFs via ReportLab |
| **Email Dispatch** | Sends complaints to the relevant municipal department |
| **Live Heatmap** | Folium-based dashboard showing complaint pins (Pending / Resolved) |
| **Supabase Backend** | Stores complaints, coordinates, and status |

---

## 📁 Project Structure

```
nagardrishti/
├── agents/             # Multi-agent orchestration (Manager-Worker pattern)
├── vision/             # YOLOv8 pothole detector + severity classifier
├── frontend/           # Streamlit UI (AI Detection + Manual Report tabs)
├── database/           # Supabase integration
├── map/                # Folium heatmap dashboard
├── utils/              # PDF generator + email sender
├── assets/             # Test images
├── config.py           # Central env config
├── .env.example        # API key template
├── requirements.txt    # Python dependencies
└── README.md
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/your-username/nagardrishti.git
cd nagardrishti
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux
```

Edit `.env` and fill in your API keys:

- **GEMINI_API_KEY** — from [Google AI Studio](https://aistudio.google.com/)
- **SUPABASE_URL** / **SUPABASE_KEY** — from your [Supabase](https://supabase.com/) project
- **SMTP_USER** / **SMTP_PASSWORD** — Gmail App Password or SMTP credentials

### 3. Run the App

```bash
streamlit run frontend/app.py
```

---

## 🧠 Architecture

```
User Upload → Gateway Agent (orchestrator)
                 ├── Veracity Agent  → EXIF check + Gemini Vision
                 ├── Vision Detector → YOLOv8 severity classification
                 ├── Legal Agent     → Draft complaint with legal citations
                 └── Action Agent    → Generate PDF + send email
```

### Severity Levels (Pothole Detection)

| Level | Condition | Label |
|-------|-----------|-------|
| 1 | Crack < 20% of frame | ✅ Safe |
| 2 | Crack 20–50% of frame | ⚠️ Risky |
| 3 | Crack > 50% of frame | 🚨 High Alert |

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.
