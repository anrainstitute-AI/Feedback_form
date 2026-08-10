# ANRA Institute - Student Feedback Portal

Flask + SQLite student feedback portal with live webcam video feedback.

## Features
- Student details
- 1-5 star overall rating
- Trainer/practical/material ratings
- Recommendation
- Written feedback
- Live webcam + microphone preview
- Browser video recording using MediaRecorder
- Video upload and local storage
- SQLite database
- Basic admin feedback page
- MySQL-ready configuration

## Run

### 1. Create environment (recommended)
Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install
```bash
pip install -r requirements.txt
```

### 3. Start
```bash
python app.py
```

Open:
- Student form: http://127.0.0.1:5000/
- Admin page: http://127.0.0.1:5000/admin/feedback
- Health check: http://127.0.0.1:5000/health

The database is created automatically at:
`database/feedback.db`

Videos are stored at:
`uploads/videos/`

## MySQL

Create:
```sql
CREATE DATABASE anra_feedback;
```

Then replace the SQLite URI in `app.py` with:
```python
app.config["SQLALCHEMY_DATABASE_URI"] = (
    "mysql+pymysql://root:YOUR_PASSWORD@localhost/anra_feedback"
)
```

Do not commit real database passwords to source control.

## Camera permissions

Modern browsers require permission for camera/microphone access. For production, serve the site over HTTPS. `localhost` is generally treated as a secure context for development.

## Production notes

Before public deployment, add:
- Admin authentication
- CSRF protection
- Secure/private video authorization
- Upload MIME/content validation
- Video duration and size limits
- Rate limiting
- HTTPS
- Cloud/object storage for videos
- Database backups
- Logging and monitoring
