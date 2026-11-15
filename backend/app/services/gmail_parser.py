"""Gmail parser: reads recent mail and moves jobs along the pipeline.

Setup:
1. Google Cloud Console -> create project -> enable Gmail API.
2. OAuth consent screen (External, add yourself as a test user).
3. Create OAuth client ID (Desktop app) -> download as backend/credentials.json.
4. Run once:  python -m app.services.gmail_parser   (opens a browser, saves token.json)

Only the read-only scope is requested.
"""
import base64
import logging
import re
from pathlib import Path

from ..database import SessionLocal
from ..models import Job, Status

log = logging.getLogger("gmail")
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BASE = Path(__file__).resolve().parents[2]

RULES: list[tuple[Status, re.Pattern]] = [
    (Status.rejected, re.compile(r"regret|unfortunately|not (be )?moving forward|unsuccessful|not selected|other candidates", re.I)),
    (Status.offer, re.compile(r"offer letter|pleased to offer|job offer", re.I)),
    (Status.interview, re.compile(r"interview|assessment|technical test|shortlisted|next round", re.I)),
    (Status.applied, re.compile(r"thank you for applying|application (has been )?received|we have received your application", re.I)),
]
ORDER = [Status.saved, Status.viewed, Status.applied, Status.interview, Status.offer, Status.rejected]


def get_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token_file, cred_file = BASE / "token.json", BASE / "credentials.json"
    creds = Credentials.from_authorized_user_file(str(token_file), SCOPES) if token_file.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(str(cred_file), SCOPES).run_local_server(port=0)
        token_file.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _body(payload) -> str:
    data = payload.get("body", {}).get("data")
    if data:
        return base64.urlsafe_b64decode(data).decode("utf-8", "ignore")
    return " ".join(_body(p) for p in payload.get("parts", []))


def classify_email(subject: str, body: str) -> Status | None:
    text = f"{subject}\n{body[:2000]}"
    for status, rx in RULES:
        if rx.search(text):
            return status
    return None


def match_job(db, sender: str, subject: str, body: str) -> Job | None:
    """Match an email to a tracked job by company name in sender/subject/body."""
    hay = f"{sender} {subject} {body[:1500]}".lower()
    candidates = db.query(Job).filter(Job.status != Status.saved).all() or db.query(Job).all()
    for job in candidates:
        company = job.company.lower().strip()
        if len(company) > 2 and company in hay:
            return job
    return None


def sync_gmail(max_messages: int = 30) -> int:
    if not (BASE / "token.json").exists():
        log.info("Gmail not authorised yet; run `python -m app.services.gmail_parser` once")
        return 0
    service = get_service()
    msgs = service.users().messages().list(
        userId="me", q="newer_than:3d -from:me", maxResults=max_messages).execute().get("messages", [])
    db, changed = SessionLocal(), 0
    try:
        for m in msgs:
            full = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
            headers = {h["name"].lower(): h["value"] for h in full["payload"]["headers"]}
            subject, sender = headers.get("subject", ""), headers.get("from", "")
            body = _body(full["payload"])
            new_status = classify_email(subject, body)
            if not new_status:
                continue
            job = match_job(db, sender, subject, body)
            if not job:
                continue
            # Never move backwards, except to rejected
            if new_status == Status.rejected or ORDER.index(new_status) > ORDER.index(job.status):
                if job.status != new_status:
                    job.status = new_status
                    job.notes = (job.notes + f"\n[auto] Gmail: '{subject}'").strip()
                    changed += 1
        db.commit()
    finally:
        db.close()
    return changed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    get_service()
    print("Authorised. Updated jobs:", sync_gmail())
