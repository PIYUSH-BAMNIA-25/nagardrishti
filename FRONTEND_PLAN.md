# NagarDrishti — Frontend & Maps Implementation Plan
> **For:** Frontend developer (friend)  
> **By:** Piyush  
> **Date:** 3 April 2026

---

## 🚫 DON'T TOUCH — Read This First

> [!CAUTION]
> **DO NOT modify any file inside these folders:**
> - `agents/` — The 4-agent AI pipeline (Gateway, Veracity, Legal, Action)
> - `vision/` — The YOLO pothole detection engine
> - `config.py` — Centralized configuration
> 
> These are fully tested and working. If you change anything there,
> the pipeline will break. If something doesn't work, tell Piyush first.

---

## 🏗️ What You Need to Do

You're working on **3 files** only:

| File | What to do |
|------|-----------|
| `frontend/app.py` | Fix the Streamlit UI — connect it to the real pipeline |
| `database/supabase_client.py` | Already written — just connect it |
| `map/geo_dashboard.py` | Already written — render in Streamlit |

---

## 📋 Setup (Before Coding)

### Step 1: Clone and Install
```bash
git clone https://github.com/<username>/nagardrishti.git
cd nagardrishti
pip install -r requirements.txt
```

### Step 2: Create `.env` file
Copy `.env.example` and fill in the values (Piyush will share the API keys separately):
```bash
cp .env.example .env
```

### Step 3: Create Supabase Table
Go to [supabase.com](https://supabase.com), open the project, go to **SQL Editor**, and run:
```sql
CREATE TABLE complaints (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at  TIMESTAMPTZ DEFAULT now(),
    complaint_id TEXT,
    category    TEXT NOT NULL,
    description TEXT,
    severity    INT,
    severity_label TEXT,
    latitude    FLOAT,
    longitude   FLOAT,
    location    TEXT,
    status      TEXT DEFAULT 'Pending',
    is_verified BOOLEAN DEFAULT FALSE,
    veracity_reason TEXT,
    image_url   TEXT,
    pdf_url     TEXT,
    email_sent  BOOLEAN DEFAULT FALSE,
    municipal_dept TEXT,
    source      TEXT DEFAULT 'citizen'
);
```

### Step 4: Test the pipeline works
```bash
python agents/gateway_agent.py
```
You should see the trust scoring output and a PDF in `reports/`.

---

## 🎯 Task 1: Fix Streamlit Frontend (`frontend/app.py`)

The current `app.py` has broken API calls. Here's what needs fixing:

### Problem 1: Wrong method name
```python
# ❌ CURRENT (broken)
result = agent.process_complaint(str(temp_path))

# ✅ FIX — use the real method
result = agent.process_citizen_report(
    image_path  = str(temp_path),
    description = "AI-detected road damage",
    location    = "User uploaded",       # or get from a text input
    issue_type  = "pothole",
)
```

### Problem 2: Wrong result fields
The pipeline returns a `ComplaintPayload` object, not a dict:
```python
# ❌ CURRENT (broken)
result.get("verified")
result.get("severity")
result.get("pdf_path")

# ✅ FIX — use object attributes
result.is_verified
result.severity_level
result.severity_label
result.pdf_path
result.email_sent
result.legal_draft
result.veracity_reason
```

### What Tab 1 (AI Detection) should do:
1. User uploads image + enters location
2. On button click → call `GatewayAgent().process_citizen_report(...)`
3. Show results:
   - If `result.is_verified == False` → show red error with `result.veracity_reason`
   - If verified → show severity badge, PDF download link, complaint text
4. Offer PDF download button using `result.pdf_path`

### What Tab 2 (Manual Report) should do:
1. User fills form (category, description, location, optional photo)
2. On submit → call `GatewayAgent().process_citizen_report(...)` with form data
3. Store result in Supabase (see Task 2)
4. Show success/failure message

### UI Features to Add:
- [ ] Location text input in Tab 1 (currently missing)
- [ ] GPS coordinates input (optional — lat/lng fields)
- [ ] PDF download button after pipeline completes
- [ ] Show trust score breakdown in an expander
- [ ] Loading spinner during pipeline execution

---

## 🎯 Task 2: Connect Supabase (`database/supabase_client.py`)

The Supabase client is already written. You just need to call it after the pipeline runs.

### Where to add it in `app.py`:
```python
from database.supabase_client import SupabaseClient

db = SupabaseClient()

# After pipeline completes:
db.insert_complaint({
    "complaint_id":    result.complaint_id,
    "category":        result.issue_type,
    "description":     result.description,
    "severity":        result.severity_level,
    "severity_label":  result.severity_label,
    "latitude":        result.latitude,
    "longitude":       result.longitude,
    "location":        result.location_text,
    "is_verified":     result.is_verified,
    "veracity_reason": result.veracity_reason,
    "pdf_url":         result.pdf_path,
    "email_sent":      result.email_sent,
    "municipal_dept":  result.municipal_dept,
    "source":          result.source,
})
```

---

## 🎯 Task 3: Show Heatmap (`map/geo_dashboard.py`)

The heatmap generator is already written. Render it in Streamlit.

### Install the required package:
```bash
pip install streamlit-folium
```

### Add a "Map" tab or sidebar section in `app.py`:
```python
from streamlit_folium import st_folium
from map.geo_dashboard import generate_heatmap
from database.supabase_client import SupabaseClient

# Add a third tab: tab_ai, tab_manual, tab_map = st.tabs([...])
with tab_map:
    st.header("📍 Complaint Heatmap")
    db = SupabaseClient()
    complaints = db.get_complaints_with_coordinates()
    
    if complaints:
        m = generate_heatmap(complaints)
        st_folium(m, width=700, height=500)
    else:
        st.info("No complaints with GPS data yet.")
```

---

## 🎯 Task 4: Add Complaint History View

Add a section in sidebar or a new tab to show all complaints:
```python
db = SupabaseClient()
all_complaints = db.get_all_complaints()

for c in all_complaints:
    status_icon = {"Pending": "🟡", "In Progress": "🔵", "Resolved": "🟢"}
    icon = status_icon.get(c["status"], "⚪")
    st.write(f"{icon} {c['complaint_id']} — {c['category']} — {c['status']}")
```

---

## 📁 Files You Can Edit

```
✅ frontend/app.py          ← Your main work
✅ map/geo_dashboard.py      ← If you want to customize the map
✅ README.md                 ← Update if needed

🚫 agents/*                  ← DO NOT TOUCH
🚫 vision/*                  ← DO NOT TOUCH  
🚫 config.py                 ← DO NOT TOUCH
```

---

## 🧪 How to Test

```bash
# Run the Streamlit app
streamlit run frontend/app.py

# Test just the pipeline (no UI)
python agents/gateway_agent.py
```

---

## 📌 Important Notes
- The Gemini API has **20 requests/day** on free tier — don't spam test
- Each pipeline run uses **~5 API calls** (severity + AI check + stock check + email lookup + legal draft)
- So you get roughly **4 full test runs per day**
- The sample image (`assets/sample_pothole.jpg`) is AI-generated — it will always be REJECTED
- To test a VERIFIED flow, take a real photo from your phone (it will have EXIF data)
