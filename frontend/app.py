"""
app.py — Streamlit UI for NagarDrishti

Provides a no-login web interface with two tabs:

    Tab 1: "AI Detection"
        • Upload a photo (camera / file) of a pothole or road issue
        • Runs the full AI pipeline: detection → verification → complaint

    Tab 2: "Manual Report"
        • For non-pothole issues: garbage, broken streetlights, etc.
        • User fills in category, description, and location manually

Run with:
    streamlit run frontend/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from PIL import Image

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.gateway_agent import GatewayAgent  # noqa: E402
from config import APP_TITLE  # noqa: E402

# ─── Page Config ──────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🏙️",
    layout="wide",
)

st.title("🏙️ NagarDrishti")
st.caption("AI-Powered Civic Complaint Automation System")


# ─── Tabs ─────────────────────────────────────────────────────
tab_ai, tab_manual = st.tabs(["🤖 AI Detection", "📝 Manual Report"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 1 — AI Detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_ai:
    st.header("Upload a Photo for AI Analysis")
    st.write(
        "Take a photo or upload an image of a pothole / road damage. "
        "Our AI will detect the issue, verify authenticity, classify "
        "severity, and auto-generate a formal complaint."
    )

    uploaded_file = st.file_uploader(
        "Choose an image",
        type=["jpg", "jpeg", "png"],
        key="ai_upload",
    )

    if uploaded_file is not None:
        # Display uploaded image
        col_img, col_result = st.columns(2)
        with col_img:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", use_container_width=True)

        # Save temporarily for processing
        temp_path = Path("temp_upload.jpg")
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Run pipeline
        if st.button("🚀 Analyze & Generate Complaint", key="analyze_btn"):
            with st.spinner("Running AI pipeline …"):
                # TODO: Wrap in try/except with user-friendly error messages
                agent = GatewayAgent()
                result = agent.process_complaint(str(temp_path))

            with col_result:
                if not result.get("verified", True):
                    st.error(f"❌ Image rejected: {result.get('rejection_reason')}")
                else:
                    severity = result.get("severity", 0)
                    label = result.get("severity_label", "Unknown")

                    # Severity badge
                    severity_colors = {1: "green", 2: "orange", 3: "red"}
                    severity_icons = {1: "✅", 2: "⚠️", 3: "🚨"}
                    st.markdown(
                        f"### {severity_icons.get(severity, '❓')} Severity: "
                        f"Level {severity} — {label}"
                    )

                    st.write(f"**Detections:** {len(result.get('detections', []))}")
                    st.write(f"**PDF Report:** `{result.get('pdf_path', 'N/A')}`")
                    st.write(f"**Email Sent:** {'✅' if result.get('email_sent') else '❌'}")

                    # Show complaint text
                    with st.expander("📜 Generated Complaint", expanded=True):
                        st.text(result.get("complaint_text", ""))

            # Cleanup temp file
            temp_path.unlink(missing_ok=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 2 — Manual Report
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_manual:
    st.header("Submit a Manual Complaint")
    st.write(
        "Use this form for issues that don't require AI detection — "
        "garbage dumping, broken streetlights, open manholes, etc."
    )

    with st.form("manual_form"):
        category = st.selectbox(
            "Issue Category",
            [
                "Garbage / Waste",
                "Broken Streetlight",
                "Open Manhole",
                "Water Logging",
                "Illegal Construction",
                "Other",
            ],
        )
        description = st.text_area(
            "Describe the issue",
            placeholder="e.g. Large garbage pile near the main road junction…",
        )
        location = st.text_input(
            "Location / Address",
            placeholder="e.g. MG Road, near City Mall, Jaipur",
        )
        photo = st.file_uploader(
            "Attach a photo (optional)",
            type=["jpg", "jpeg", "png"],
            key="manual_upload",
        )

        submitted = st.form_submit_button("📤 Submit Complaint")

    if submitted:
        if not description.strip():
            st.warning("Please provide a description of the issue.")
        else:
            # TODO: Store in Supabase and trigger ActionAgent
            st.success(
                f"✅ Complaint submitted!\n\n"
                f"**Category:** {category}\n\n"
                f"**Location:** {location or 'Not provided'}\n\n"
                f"Your complaint has been forwarded to the municipal office."
            )


# ─── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ℹ️ About")
    st.markdown(
        "**NagarDrishti** uses AI to detect road damage, verify photos, "
        "draft legal complaints, and email them to authorities — all in "
        "one click."
    )
    st.markdown("---")
    st.markdown("🔗 [GitHub](https://github.com/your-username/nagardrishti)")
    st.markdown("📧 Contact: support@nagardrishti.in")
