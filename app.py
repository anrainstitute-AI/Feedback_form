import os
import uuid
import smtplib
from datetime import datetime
from email.message import EmailMessage

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "videos")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

# ============================================================
# EMAIL CONFIGURATION
# Set these as Environment Variables on Render.
#
# EMAIL_SENDER       = your Gmail address
# EMAIL_PASSWORD     = Gmail App Password (NOT normal password)
# FEEDBACK_EMAIL     = email address where feedback should arrive
# SMTP_SERVER        = smtp.gmail.com
# SMTP_PORT          = 465
# ============================================================

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
FEEDBACK_EMAIL = os.getenv("FEEDBACK_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))


def send_feedback_email(feedback_data, video_path=None):
    """Send feedback details by email, optionally attaching the video."""

    if not EMAIL_SENDER or not EMAIL_PASSWORD or not FEEDBACK_EMAIL:
        raise RuntimeError(
            "Email configuration is missing. "
            "Set EMAIL_SENDER, EMAIL_PASSWORD and FEEDBACK_EMAIL."
        )

    msg = EmailMessage()

    student_name = feedback_data.get("student_name") or "Student"
    course = feedback_data.get("course") or "Not provided"

    msg["Subject"] = f"New Student Feedback - {student_name} - {course}"
    msg["From"] = EMAIL_SENDER
    msg["To"] = FEEDBACK_EMAIL

    def value(key):
        return feedback_data.get(key) or "Not provided"

    recommend = feedback_data.get("recommend")
    if recommend == "yes":
        recommend_text = "Yes"
    elif recommend == "no":
        recommend_text = "No"
    else:
        recommend_text = "Not provided"

    submitted_at = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

    body = f"""
NEW STUDENT FEEDBACK
====================

Student Name: {value("student_name")}
Email: {value("email")}
Mobile: {value("mobile")}
Course: {value("course")}
Trainer: {value("trainer")}

RATINGS
-------
Overall Rating: {value("overall_rating")}
Trainer Rating: {value("trainer_rating")}
Practical Rating: {value("practical_rating")}
Material Rating: {value("material_rating")}

Would Recommend: {recommend_text}

WRITTEN FEEDBACK
----------------
{value("written_feedback")}

Submitted At: {submitted_at}

Video Attached: {"Yes" if video_path else "No"}
"""

    msg.set_content(body)

    if video_path and os.path.exists(video_path):
        with open(video_path, "rb") as video_file:
            video_data = video_file.read()

        filename = os.path.basename(video_path)

        # Determine a reasonable MIME type from the extension.
        ext = os.path.splitext(filename)[1].lower()
        subtype = {
            ".mp4": "mp4",
            ".webm": "webm",
            ".mov": "quicktime",
        }.get(ext, "octet-stream")

        maintype = "video" if ext in {".mp4", ".webm", ".mov"} else "application"

        msg.add_attachment(
            video_data,
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )

    # Gmail SMTP over SSL.
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)


@app.route("/")
def index():
    return render_template("feedback.html")


@app.route("/submit-feedback", methods=["POST"])
def submit_feedback():
    video_path = None

    try:
        student_name = request.form.get("student_name", "").strip()

        if not student_name:
            return jsonify(
                success=False,
                message="Student name is required."
            ), 400

        def rating(name):
            value = request.form.get(name)
            return int(value) if value else None

        recommend = request.form.get("recommend")
        recommend_value = (
            "yes" if recommend == "yes"
            else "no" if recommend == "no"
            else None
        )

        written_feedback = (
            request.form.get("written_feedback", "").strip() or None
        )

        # ----------------------------------------------------
        # Save uploaded video temporarily.
        # It is attached to the email and then removed.
        # ----------------------------------------------------
        video = request.files.get("video")

        if video and video.filename:
            original = secure_filename(video.filename)
            ext = os.path.splitext(original)[1].lower()

            if ext not in {".webm", ".mp4", ".mov"}:
                return jsonify(
                    success=False,
                    message="Invalid video format. Use MP4, WebM or MOV."
                ), 400

            filename = f"{uuid.uuid4().hex}{ext}"
            video_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            video.save(video_path)

        feedback_data = {
            "student_name": student_name,
            "email": request.form.get("email"),
            "mobile": request.form.get("mobile"),
            "course": request.form.get("course"),
            "trainer": request.form.get("trainer"),
            "overall_rating": rating("overall_rating"),
            "trainer_rating": rating("trainer_rating"),
            "practical_rating": rating("practical_rating"),
            "material_rating": rating("material_rating"),
            "recommend": recommend_value,
            "written_feedback": written_feedback,
        }

        # ----------------------------------------------------
        # Send feedback directly to your email.
        # ----------------------------------------------------
        send_feedback_email(feedback_data, video_path)

        return jsonify(
            success=True,
            message="Thank you! Your feedback has been submitted successfully."
        )

    except Exception as exc:
        app.logger.exception("Feedback submission failed: %s", exc)

        return jsonify(
            success=False,
            message="Unable to submit feedback. Please try again."
        ), 500

    finally:
        # Remove temporary video after email is sent.
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except OSError:
                app.logger.exception(
                    "Could not remove temporary video: %s",
                    video_path
                )


@app.route("/admin/feedback")
def admin_feedback():
    # Email-only version: there is no database/admin list.
    return """
    <h2>Email Feedback System</h2>
    <p>Feedback is delivered directly to the configured feedback email address.</p>
    """


@app.route("/health")
def health():
    return jsonify(status="ok")


if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000"))
    )
