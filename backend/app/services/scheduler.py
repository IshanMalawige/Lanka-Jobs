import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import settings
from ..scrapers.runner import run_all_scrapers
from .gmail_parser import sync_gmail

log = logging.getLogger("scheduler")
scheduler = BackgroundScheduler()


def _safe_gmail():
    try:
        sync_gmail()
    except Exception as e:
        log.warning("gmail sync failed: %s", e)


def start():
    scheduler.add_job(run_all_scrapers, "interval", minutes=settings.scrape_interval_minutes,
                      id="scrape", max_instances=1, next_run_time=datetime.now())
    scheduler.add_job(_safe_gmail, "interval", minutes=settings.gmail_sync_interval_minutes,
                      id="gmail", max_instances=1)
    scheduler.start()
