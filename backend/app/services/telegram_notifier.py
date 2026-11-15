import logging
from datetime import datetime
from threading import Lock

import requests
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Job, TelegramNotification
from .cv_profile import get_profile
from .skill_gap import analyze_job

log = logging.getLogger(__name__)
_delivery_lock = Lock()


def _configured() -> bool:
    return bool(
        settings.telegram_bot_token.get_secret_value().strip()
        and settings.telegram_chat_id.strip()
    )


def queue_high_match_job(db: Session, job: Job) -> bool:
    """Queue a newly discovered job once when its skill match exceeds the threshold."""
    if not _configured() or db.get(TelegramNotification, job.id):
        return False

    profile = get_profile()
    user_skills = profile["skills"] if profile else None
    result = analyze_job(job, user_skills=user_skills)
    match_percent = result["match_percent"]
    if match_percent is None or match_percent <= settings.telegram_match_threshold:
        return False

    db.add(TelegramNotification(
        job_id=job.id,
        match_percent=match_percent,
        estimated=bool(result.get("estimated")),
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.get(TelegramNotification, job.id):
            return False
        raise
    return True


def send_pending_notifications(db: Session) -> int:
    """Send queued Telegram messages and retain failures for the next scrape cycle."""
    if not _configured():
        return 0

    sent = 0
    token = settings.telegram_bot_token.get_secret_value().strip()
    chat_id = settings.telegram_chat_id.strip()
    with _delivery_lock:
        pending = (
            db.query(TelegramNotification, Job)
            .join(Job, Job.id == TelegramNotification.job_id)
            .filter(TelegramNotification.status == "pending")
            .order_by(TelegramNotification.created_at, TelegramNotification.job_id)
            .all()
        )
        for notification, job in pending:
            text = (
                f"{'Estimated high-match job' if notification.estimated else 'High-match job'} "
                f"({notification.match_percent}%)\n"
                f"{job.title}\n"
                f"Company: {job.company or 'Not listed'}\n"
                f"View job: {job.url}"
            )
            try:
                response = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": text},
                    timeout=10,
                )
                response.raise_for_status()
                result = response.json()
            except requests.RequestException as exc:
                log.warning(
                    "Telegram delivery failed for job_id=%s (%s); it will be retried.",
                    job.id,
                    type(exc).__name__,
                )
                continue
            except ValueError:
                log.warning("Telegram returned invalid JSON for job_id=%s; it will be retried.", job.id)
                continue

            if not isinstance(result, dict) or result.get("ok") is not True:
                log.warning("Telegram rejected the message for job_id=%s; it will be retried.", job.id)
                continue

            notification.status = "sent"
            notification.sent_at = datetime.utcnow()
            try:
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                log.exception("Could not save Telegram delivery state for job_id=%s.", job.id)
                continue
            sent += 1
    return sent
