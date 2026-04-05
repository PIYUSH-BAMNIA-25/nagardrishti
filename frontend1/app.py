import os
import sys
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Rate limiting to prevent API abuse
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
    try:
        all_complaints = db.get_all_complaints() or []
        total = len(all_complaints)
        verified = sum(1 for c in all_complaints 
                      if c.get('is_verified') == True)
        verified_pct = round((verified/total*100)) if total > 0 else 0
        stats = {
            "total_complaints" : total,
            "verified_pct"     : verified_pct,
            "depts_connected"  : 8,
        }
    except:
        stats = {
            "total_complaints" : 0,
            "verified_pct"     : 0,
            "depts_connected"  : 8,
        }
    return stats


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
    from config import MUNICIPAL_EMAILS

    departments_list = [
        {"name": "Roads & Infrastructure", 
         "email": "tailaung16@gmail.com",
         "status": "Active"},
        {"name": "Sanitation & Waste", 
         "email": "tailaung16@gmail.com",
         "status": "Active"},
        {"name": "Electrical & Lighting", 
         "email": "tailaung16@gmail.com",
         "status": "Active"},
        {"name": "Public Works (PWD)", 
         "email": "tailaung16@gmail.com",
         "status": "Active"},
        {"name": "Drainage & Sewerage", 
         "email": "tailaung16@gmail.com",
         "status": "Active"},
    ]
    return render_template('departments.html', 
                           departments=departments_list)

@app.route("/complaint-map")
def complaint_map():
    # Fetch complaints with GPS data for dynamic map markers
    complaints = safe_get_complaints_with_coordinates()
    return render_template("tab3_map.html", complaints=complaints)

@app.route("/history")
def history():
    try:
        all_complaints = db.get_all_complaints() or []
        display_complaints = [
            c for c in all_complaints
            if c.get('is_verified') == True
            or c.get('source') == 'manual_text_only'
        ]
        return render_template("tab4_history.html", complaints=display_complaints)
    except Exception as e:
        print(f"[History] Error: {e}")
        return render_template("tab4_history.html", complaints=[])

@app.route("/history/<complaint_id>")
def complaint_detail(complaint_id):
    try:
        complaint = db.get_complaint_by_public_id(complaint_id)
        if not complaint:
            return "Complaint not found", 404

        # Set PDF filename for download
        if complaint.get('is_verified'):
            complaint['pdf_filename'] = f"{complaint_id}_report.pdf"
        else:
            complaint['pdf_filename'] = f"{complaint_id}_REJECTED.pdf"

        # Add display flags
        complaint['show_email_actions'] = complaint.get('is_verified', False)

        # Normalize field names for template compatibility
        complaint['issue_type']     = complaint.get('category')
        complaint['severity_level'] = complaint.get('severity')
        complaint['location_text']  = complaint.get('location')

        return render_template("complaint_detail.html", complaint=complaint)
    except Exception as e:
        print(f"[Detail] Error: {e}")
        return f"Error loading complaint: {e}", 500


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
    try:
        all_complaints = db.get_all_complaints() or []
        geo_complaints = []
        for c in all_complaints:
            lat = c.get('latitude')
            lng = c.get('longitude')
            # Only show verified complaints with real GPS
            if (c.get('is_verified') == True and
                lat and lng and
                float(lat) != 0.0 and
                float(lng) != 0.0):
                geo_complaints.append({
                    "complaint_id"  : c.get('complaint_id'),
                    "issue_type"    : c.get('category'),
                    "severity_level": c.get('severity'),
                    "severity_label": c.get('severity_label'),
                    "location_text" : c.get('location'),
                    "latitude"      : float(lat),
                    "longitude"     : float(lng),
                    "status"        : c.get('status', 'Pending'),
                })
        return jsonify({"success": True, "complaints": geo_complaints})
    except Exception as e:
        return jsonify({"success": False, "complaints": [], "error": str(e)})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API: AI Pipeline Analysis
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/analyze", methods=["POST"])
@limiter.limit("10 per minute")
def api_analyze():
    if 'image' not in request.files:
        return jsonify({"success": False, "error": "No image uploaded"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "error": "Empty filename"}), 400

    if not allowed_file(file.filename):
        return jsonify({
            "success": False, 
            "error": "Only JPG and PNG files are allowed"
        }), 400

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

        # Only save VERIFIED complaints to Supabase
        # Rejected complaints are logged but NOT stored
        if result.is_verified:
            try:
                pdf_filename = os.path.basename(result.pdf_path) if result.pdf_path else f"{result.complaint_id}_report.pdf"
                complaint_data = {
                    "complaint_id"   : result.complaint_id,
                    "category"       : result.issue_type,
                    "description"    : result.description,
                    "severity"       : result.severity_level,
                    "severity_label" : result.severity_label,
                    "latitude"       : latitude if latitude != 0.0 else None,
                    "longitude"      : longitude if longitude != 0.0 else None,
                    "location"       : result.location_text,
                    "status"         : "Pending",
                    "is_verified"    : True,
                    "veracity_reason": result.veracity_reason,
                    "image_url"      : filepath if filepath else None,
                    "pdf_url"        : pdf_filename,
                    "email_sent"     : getattr(result, 'email_sent', False),
                    "municipal_dept" : result.municipal_dept,
                    "source"         : "ai_detection",
                }
                db.insert_complaint(complaint_data)
                print(f"[Analyze] Saved verified complaint {result.complaint_id} to Supabase")
            except Exception as e:
                print(f"[Analyze] Supabase save error: {e}")
        else:
            print(f"[Analyze] Complaint {result.complaint_id} REJECTED — not saved to Supabase")

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
@limiter.limit("10 per minute")
def api_manual_report():
    try:
        description  = request.form.get("description", "")
        location     = request.form.get("location", "")
        category     = request.form.get("category", "Other")
        latitude     = float(request.form.get("latitude", 0.0) or 0.0)
        longitude    = float(request.form.get("longitude", 0.0) or 0.0)

        image_path = ""
        if "image" in request.files:
            file = request.files["image"]
            if file.filename:
                fname = secure_filename(file.filename)
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
                file.save(image_path)

        # Run full AI pipeline (same as AI route)
        result = gateway_agent.process_citizen_report(
            image_path  = image_path,
            description = description,
            location    = location,
            issue_type  = category,
            latitude    = latitude,
            longitude   = longitude,
        )

        # Manual report storage logic
        try:
            pdf_filename = os.path.basename(result.pdf_path) if result.pdf_path else f"{result.complaint_id}_report.pdf"
            complaint_data = {
                "complaint_id"   : result.complaint_id,
                "category"       : result.issue_type,
                "description"    : result.description,
                "severity"       : result.severity_level,
                "severity_label" : result.severity_label,
                "latitude"       : latitude if latitude != 0.0 else None,
                "longitude"      : longitude if longitude != 0.0 else None,
                "location"       : result.location_text or location,
                "status"         : "Pending",
                "is_verified"    : result.is_verified,
                "veracity_reason": result.veracity_reason,
                "image_url"      : image_path if image_path else None,
                "pdf_url"        : pdf_filename,
                "email_sent"     : getattr(result, 'email_sent', False),
                "municipal_dept" : result.municipal_dept,
                "source"         : "citizen_manual",
            }

            # Manual reports with images go through full pipeline
            if image_path and result.is_verified:
                # Save verified manual complaints normally
                complaint_data['is_verified'] = True
                db.insert_complaint(complaint_data)
                print(f"[Analyze] Saved verified manual complaint {result.complaint_id} to Supabase")
            elif not image_path:
                # Text-only manual reports: save as pending
                complaint_data['is_verified'] = False
                complaint_data['source'] = 'manual_text_only'
                db.insert_complaint(complaint_data)
                print(f"[Analyze] Saved text-only manual complaint {result.complaint_id} to Supabase")
            else:
                # Has image but rejected — don't save
                print(f"[Analyze] Manual complaint {result.complaint_id} REJECTED — not saved to Supabase")

        except Exception as e:
            print(f"[Analyze] Supabase save error: {e}")

        if result.is_verified:
            return jsonify({
                "success":        True,
                "complaint_id":   result.complaint_id,
                "severity_level": result.severity_level,
                "severity_label": result.severity_label,
                "is_verified":    True,
                "pdf_url":        f"/reports/{os.path.basename(result.pdf_path)}" if result.pdf_path else "",
                "message":        "Complaint submitted and verified successfully",
            })
        else:
            return jsonify({
                "success":       False,
                "complaint_id":  result.complaint_id,
                "is_verified":   False,
                "message":       f"Complaint rejected: {result.veracity_reason}",
            }), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Static file serving (favicon, etc.)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/reports/<path:filename>")
def download_report(filename):
    """Serve generated PDF reports for download."""
    return send_from_directory(REPORTS_DIR, filename, as_attachment=True)


@app.route("/favicon.png")
def favicon():
    return send_from_directory(str(STITCH_DIR), "favicon.png")


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
