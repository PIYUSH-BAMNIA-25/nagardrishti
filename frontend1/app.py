import os
import sys
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory

from werkzeug.utils import secure_filename

# Add the project root to sys.path so we can import internal modules
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()  # Load all secrets from .env

from agents.gateway_agent import GatewayAgent
from database.supabase_client import SupabaseClient
from config import REPORTS_DIR

STITCH_DIR = Path(__file__).parent / "stitch_pages"

# Configure Flask to use stitch_pages as the template folder
app = Flask(__name__, template_folder=str(STITCH_DIR), static_folder=str(STITCH_DIR))
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-dev-secret-key-nagardrishti")

# Ensure REPORTS_DIR exists for PDF output
os.makedirs(REPORTS_DIR, exist_ok=True)
UPLOAD_FOLDER = ROOT / "reports" / "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)

# Initialize singletons
gateway_agent = GatewayAgent()
db = SupabaseClient()


def safe_get_all_complaints():
    try:
        return db.get_all_complaints()
    except Exception:
        return []


def safe_get_complaint_by_public_id(complaint_id: str):
    try:
        return db.get_complaint_by_public_id(complaint_id)
    except Exception:
        return None


def safe_get_complaints_with_coordinates():
    try:
        return db.get_complaints_with_coordinates()
    except Exception:
        return []


def build_home_stats():
    complaints = safe_get_all_complaints()
    total_complaints = len(complaints)
    verified_count = sum(1 for complaint in complaints if complaint.get("is_verified"))
    connected_departments = len(
        {
            (complaint.get("municipal_dept") or "").strip()
            for complaint in complaints
            if (complaint.get("municipal_dept") or "").strip()
        }
    )
    verified_rate = round((verified_count / total_complaints) * 100) if total_complaints else 0

    return {
        "total_complaints": total_complaints,
        "verified_rate": verified_rate,
        "connected_departments": connected_departments,
    }


def build_departments_context():
    complaints = safe_get_all_complaints()
    departments = sorted(
        {
            (complaint.get("municipal_dept") or "").strip()
            for complaint in complaints
            if (complaint.get("municipal_dept") or "").strip()
        }
    )

    if not departments:
        departments = ["PWD", "Sanitation", "Electrical", "Water Supply", "General"]

    department_cards = []
    for department in departments:
        slug = (
            department.lower()
            .replace("&", "and")
            .replace("/", " ")
            .replace("(", "")
            .replace(")", "")
            .replace("  ", " ")
            .strip()
            .replace(" ", "_")
        )
        department_cards.append(
            {
                "name": department,
                "email": f"{slug}@nagardrishti.in",
            }
        )

    return {
        "departments": department_cards,
        "department_count": len(department_cards),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Page Routes — Core pages that have redesigned templates
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/")
def home():
    return render_template("home.html", stats=build_home_stats())

@app.route("/ai-detection")
def ai_detection():
    return render_template("tab1_initial.html")

@app.route("/ai-detection/verified")
def ai_verified():
    return render_template("tab1_verified.html")

@app.route("/ai-detection/rejected")
def ai_rejected():
    return render_template("tab1_rejected.html")

@app.route("/manual-report")
def manual_report():
    return render_template("tab2_form.html")

@app.route("/manual-report/submitted")
def manual_report_submitted():
    return render_template("tab2_submitted.html")

@app.route("/departments")
def departments():
    return render_template("departments.html", **build_departments_context())

@app.route("/complaint-map")
def complaint_map():
    # Fetch complaints with GPS data for dynamic map markers
    complaints = safe_get_complaints_with_coordinates()
    return render_template("tab3_map.html", complaints=complaints)

@app.route("/history")
def history():
    # Fetch all complaints from Supabase for the history table
    complaints = safe_get_all_complaints()
    return render_template("tab4_history.html", complaints=complaints)

@app.route("/history/<complaint_id>")
def complaint_detail(complaint_id):
    complaint = safe_get_complaint_by_public_id(complaint_id)
    if not complaint:
        # Fallback: build complaint object from URL query params (for demo use)
        complaint = {
            "complaint_id": complaint_id,
            "category": request.args.get("category", "Complaint"),
            "description": request.args.get("description", "Complaint details are unavailable."),
            "severity": request.args.get("severity", "N/A"),
            "severity_label": request.args.get("severity_label", ""),
            "location": request.args.get("location", "Unknown location"),
            "status": request.args.get("status", "Pending"),
            "municipal_dept": request.args.get("municipal_dept", "Municipal Department"),
            "source": request.args.get("source", "Citizen Portal"),
            "created_at": request.args.get("created_at", datetime.now().isoformat()),
            "latitude": request.args.get("latitude", ""),
            "longitude": request.args.get("longitude", ""),
            "pdf_url": request.args.get("pdf_url", ""),
            "email_sent": request.args.get("email_sent", "false").lower() == "true",
            "is_verified": request.args.get("is_verified", "true").lower() == "true",
            "issue_type": request.args.get("issue_type", request.args.get("category", "Complaint")),
        }
    return render_template("complaint_detail.html", complaint=complaint)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API: Fetch complaints as JSON (for dynamic map/frontend)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/complaints", methods=["GET"])
def api_get_complaints():
    """Returns all complaints as JSON — usable by the map and history pages."""
    complaints = safe_get_all_complaints()
    return jsonify({"success": True, "data": complaints})


@app.route("/api/complaints/geo", methods=["GET"])
def api_get_geo_complaints():
    """Returns only complaints with GPS coordinates — for map markers."""
    complaints = safe_get_complaints_with_coordinates()
    return jsonify({"success": True, "data": complaints})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API: AI Pipeline Analysis
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No image uploaded"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "Empty filename"}), 400

    location = request.form.get("location", "Unknown Location")
    issue_type = request.form.get("issue_type", "pothole")
    latitude = request.form.get("latitude", 0.0)
    longitude = request.form.get("longitude", 0.0)

    try:
        latitude = float(latitude) if latitude else 0.0
    except (ValueError, TypeError):
        latitude = 0.0
    try:
        longitude = float(longitude) if longitude else 0.0
    except (ValueError, TypeError):
        longitude = 0.0

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        # Run through the full AI pipeline: Gateway → Veracity → Legal → Action
        result = gateway_agent.process_citizen_report(
            image_path=filepath,
            description="AI-detected user upload",
            location=location,
            issue_type=issue_type,
            latitude=latitude,
            longitude=longitude,
        )

        # Save to Supabase
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

        return jsonify({
            "success": True,
            "data": {
                "is_verified": result.is_verified,
                "reason": result.veracity_reason,
                "complaint_id": result.complaint_id,
                "severity_label": result.severity_label
            }
        })

    except Exception as e:
        return jsonify({"success": False, "error": f"AI Pipeline Failed: {str(e)}"}), 500


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API: Re-send Complaint Email
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/resend-email/<complaint_id>", methods=["POST"])
def api_resend_email(complaint_id):
    """Re-sends the complaint email for a given complaint ID."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders
    from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SENDER_EMAIL, SENDER_NAME, TEST_EMAIL_OVERRIDE

    complaint = safe_get_complaint_by_public_id(complaint_id)
    if not complaint:
        return jsonify({"success": False, "error": "Complaint not found"}), 404

    if not SMTP_USER or not SMTP_PASS:
        return jsonify({"success": False, "error": "SMTP credentials not configured"}), 500

    recipient = TEST_EMAIL_OVERRIDE if TEST_EMAIL_OVERRIDE else os.getenv("DEFAULT_RECIPIENT", "municipal_office@example.com")
    try:
        msg = MIMEMultipart("mixed")
        msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg["To"] = recipient
        msg["Subject"] = (
            f"[NagarDrishti] Re-send: Complaint {complaint_id} — "
            f"{complaint.get('category', 'Civic Issue')} at {complaint.get('location', 'Unknown')}"
        )

        body_text = (
            f"This is a re-sent notification for complaint {complaint_id}.\n\n"
            f"Category: {complaint.get('category', 'N/A')}\n"
            f"Location: {complaint.get('location', 'N/A')}\n"
            f"Description: {complaint.get('description', 'N/A')}\n"
            f"Severity: {complaint.get('severity_label', 'N/A')}\n"
            f"Status: {complaint.get('status', 'Pending')}\n\n"
            f"— NagarDrishti AI Civic System"
        )
        msg.attach(MIMEText(body_text, "plain"))

        # Attach PDF if it exists
        pdf_url = complaint.get("pdf_url", "")
        if pdf_url and os.path.exists(pdf_url):
            with open(pdf_url, "rb") as f:
                pdf_part = MIMEBase("application", "octet-stream")
                pdf_part.set_payload(f.read())
            encoders.encode_base64(pdf_part)
            pdf_part.add_header(
                "Content-Disposition",
                f"attachment; filename={os.path.basename(pdf_url)}"
            )
            msg.attach(pdf_part)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SENDER_EMAIL, recipient, msg.as_string())

        return jsonify({"success": True, "message": f"Email re-sent to {recipient}"})

    except Exception as e:
        return jsonify({"success": False, "error": f"Email failed: {str(e)}"}), 500

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API: Manual Report Submission
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/manual-report", methods=["POST"])
def api_manual_report():
    data = request.json or request.form
    complaint_id = f"ND-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    category = data.get("category", "Other")
    description = data.get("description", "")
    location = data.get("location", "Unknown location")
    municipal_dept = data.get("municipal_department") or data.get("department") or "General"
    latitude = data.get("latitude") or None
    longitude = data.get("longitude") or None
    attachment_name = None

    if "image" in request.files:
        image = request.files["image"]
        if image and image.filename:
            attachment_name = secure_filename(image.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], attachment_name)
            image.save(filepath)

    complaint_record = {
        "complaint_id": complaint_id,
        "category": category,
        "description": description,
        "severity": 1,
        "severity_label": "Medium",
        "latitude": latitude,
        "longitude": longitude,
        "location": location,
        "status": "Pending",
        "image_url": attachment_name,
        "pdf_url": "",
        "email_sent": False,
        "municipal_dept": municipal_dept,
        "source": "manual_report",
        "is_verified": True,
    }

    try:
        db.insert_complaint(complaint_record)
    except Exception:
        pass

    return jsonify({
        "success": True,
        "message": "Manual report saved",
        "data": {
            "complaint_id": complaint_id,
            "category": category,
            "location": location,
            "municipal_dept": municipal_dept,
            "attachment_name": attachment_name or "No attachment uploaded",
        }
    })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Static file serving (favicon, etc.)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/favicon.png")
def favicon():
    return send_from_directory(str(STITCH_DIR), "favicon.png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
