import os
import uuid
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "videos")
DATABASE_FOLDER = os.path.join(BASE_DIR, "database")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATABASE_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + os.path.join(DATABASE_FOLDER, "feedback.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

db = SQLAlchemy(app)


class StudentFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150))
    mobile = db.Column(db.String(30))
    course = db.Column(db.String(150))
    trainer = db.Column(db.String(150))
    overall_rating = db.Column(db.Integer)
    trainer_rating = db.Column(db.Integer)
    practical_rating = db.Column(db.Integer)
    material_rating = db.Column(db.Integer)
    recommend = db.Column(db.Boolean)
    written_feedback = db.Column(db.Text)
    video_filename = db.Column(db.String(255))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)


@app.route("/")
def index():
    return render_template("feedback.html")


@app.route("/submit-feedback", methods=["POST"])
def submit_feedback():
    try:
        student_name = request.form.get("student_name", "").strip()
        if not student_name:
            return jsonify(success=False, message="Student name is required."), 400

        def rating(name):
            value = request.form.get(name)
            return int(value) if value else None

        recommend = request.form.get("recommend")
        recommend_value = True if recommend == "yes" else False if recommend == "no" else None

        # written_feedback comes from the textarea. Strip it and fall back to
        # None (not empty string) so it's easy to tell "not filled in" apart
        # from "filled in with nothing" when you look at the DB.
        written_feedback = request.form.get("written_feedback", "").strip() or None

        video_filename = None
        video = request.files.get("video")

        if video and video.filename:
            original = secure_filename(video.filename)
            ext = os.path.splitext(original)[1].lower()
            if ext not in {".webm", ".mp4", ".mov"}:
                return jsonify(success=False, message="Invalid video format."), 400

            video_filename = f"{uuid.uuid4().hex}{ext}"
            video.save(os.path.join(UPLOAD_FOLDER, video_filename))

        feedback = StudentFeedback(
            student_name=student_name,
            email=request.form.get("email"),
            mobile=request.form.get("mobile"),
            course=request.form.get("course"),
            trainer=request.form.get("trainer"),
            overall_rating=rating("overall_rating"),
            trainer_rating=rating("trainer_rating"),
            practical_rating=rating("practical_rating"),
            material_rating=rating("material_rating"),
            recommend=recommend_value,
            written_feedback=written_feedback,
            video_filename=video_filename,
        )
        db.session.add(feedback)
        db.session.commit()

        return jsonify(
            success=True,
            message="Thank you! Your feedback has been submitted.",
            feedback_id=feedback.id,
        )

    except Exception as exc:
        db.session.rollback()
        app.logger.exception("Feedback submission failed: %s", exc)
        return jsonify(success=False, message="Server error while submitting feedback."), 500


@app.route("/videos/<path:filename>")
def uploaded_video(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route("/admin/feedback")
def admin_feedback():
    feedbacks = StudentFeedback.query.order_by(
        StudentFeedback.submitted_at.desc()
    ).all()
    return render_template("admin_feedback.html", feedbacks=feedbacks)


@app.route("/health")
def health():
    return jsonify(status="ok")


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
