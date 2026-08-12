import os
import uuid
import smtplib
from datetime import datetime
from email.message import EmailMessage

import cloudinary
import cloudinary.uploader

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

# Gmail settings - configure these in Render Environment Variables
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Gmail App Password, no spaces
FEEDBACK_EMAIL = os.getenv("FEEDBACK_EMAIL")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))

# Cloudinary settings - configure these in Render Environment Variables
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}


def validate_config():
    missing = []
    for name, value in {
        "EMAIL_SENDER": EMAIL_SENDER,
        "EMAIL_PASSWORD": EMAIL_PASSWORD,
        "FEEDBACK_EMAIL": FEEDBACK_EMAIL,
        "CLOUDINARY_CLOUD_NAME": CLOUDINARY_CLOUD_NAME,
        "CLOUDINARY_API_KEY": CLOUDINARY_API_KEY,
        "CLOUDINARY_API_SECRET": CLOUDINARY_API_SECRET,
    }.items():
        if not value:
            missing.append(name)

    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))


def upload_video(video):
    if not video or not video.filename:
        return None

    filename = secure_filename(video.filename)
    extension = os.path.splitext(filename)[1].lower()

    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError("Invalid video format. Please use MP4, WebM or MOV.")

    result = cloudinary.uploader.upload(
        video,
        resource_type="video",
        public_id=f"student_feedback/{uuid.uuid4().hex}",
        overwrite=False
    )

    return result.get("secure_url")


def send_feedback_email(data, video_url=None):
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not FEEDBACK_EMAIL:
        raise RuntimeError("Gmail environment variables are missing.")

    def value(key):
        return data.get(key) or "Not provided"

    recommend = data.get("recommend")
    recommend_text = "Yes" if recommend == "yes" else "No" if recommend == "no" else "Not provided"

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

Submitted At: {datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")}

VIDEO
-----
{video_url if video_url else "No video was submitted."}
"""

    msg = EmailMessage()
    msg["Subject"] = f"New Student Feedback - {value('student_name')} - {value('course')}"
    msg["From"] = EMAIL_SENDER
    msg["To"] = FEEDBACK_EMAIL
    msg.set_content(body)

    # Short timeout prevents a mail server problem from blocking Gunicorn.
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)


@app.route("/")
def index():
    return render_template("feedback.html")


@app.route("/submit-feedback", methods=["POST"])
def submit_feedback():
    try:
        student_name = request.form.get("student_name", "").strip()

        if not student_name:
            return jsonify(success=False, message="Student name is required."), 400

        def rating(field):
            value = request.form.get(field)
            try:
                return int(value) if value else None
            except ValueError:
                return None

        recommend = request.form.get("recommend")
        if recommend not in ("yes", "no"):
            recommend = None

        data = {
            "student_name": student_name,
            "email": request.form.get("email"),
            "mobile": request.form.get("mobile"),
            "course": request.form.get("course"),
            "trainer": request.form.get("trainer"),
            "overall_rating": rating("overall_rating"),
            "trainer_rating": rating("trainer_rating"),
            "practical_rating": rating("practical_rating"),
            "material_rating": rating("material_rating"),
            "recommend": recommend,
            "written_feedback": request.form.get("written_feedback", "").strip() or None,
        }

        # Video goes to Cloudinary, not Gmail.
        video_url = upload_video(request.files.get("video"))

        # Gmail receives only the text feedback and the Cloudinary URL.
        send_feedback_email(data, video_url)

        return jsonify(
            success=True,
            message="Thank you! Your feedback has been submitted successfully."
        )

    except ValueError as exc:
        app.logger.warning("Validation error: %s", exc)
        return jsonify(success=False, message=str(exc)), 400

    except smtplib.SMTPAuthenticationError:
        app.logger.exception("Gmail authentication failed")
        return jsonify(
            success=False,
            message="Gmail authentication failed. Check your Gmail App Password."
        ), 500

    except smtplib.SMTPException:
        app.logger.exception("Gmail SMTP error")
        return jsonify(
            success=False,
            message="Gmail could not send the message. Check SMTP settings."
        ), 500

    except Exception:
        app.logger.exception("Feedback submission failed")
        return jsonify(
            success=False,
            message="Server error while processing feedback. Please check Render logs."
        ), 500


@app.route("/admin/feedback")
def admin_feedback():
    return """
    <h2>Email Feedback System</h2>
    <p>Feedback is delivered to the configured email address.</p>
    <p>Videos are stored in Cloudinary and their secure links are included in the email.</p>
    """


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.errorhandler(413)
def request_too_large(error):
    return jsonify(
        success=False,
        message="The uploaded video is too large. Maximum size is 100 MB."
    ), 413


if __name__ == "__main__":
    app.run(
        debug=True,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000"))
    )
