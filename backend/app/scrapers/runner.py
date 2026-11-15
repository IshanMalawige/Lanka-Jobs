import logging
from datetime import datetime
from time import perf_counter

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..filters import classify
from ..models import Job
from ..services.job_details import _html_text, needs_job_details, refresh_single_job_details
from ..services.telegram_notifier import queue_high_match_job, send_pending_notifications
from .itpro import ITProScraper
from .linkedin import LinkedInScraper
from .topjobs import TopJobsScraper
from .xpress import XpressScraper

log = logging.getLogger("scraper")
SCRAPERS = [TopJobsScraper, ITProScraper, XpressScraper, LinkedInScraper]


def _enrich_job(db: Session, job: Job) -> None:
    refresh_single_job_details(db, job, force=True)


def save_raw_jobs(db: Session, raw_jobs) -> int:
    """Store listings immediately, then enrich descriptions without holding a DB lock."""
    added = 0
    for rj in raw_jobs:
        # Banking openings span all departments. The configured TopJobs, ITPro,
        # and Xpress pages are IT categories, so keep their listings even when a
        # title is broader than the detailed target-role labels used by LinkedIn.
        category = classify(rj.title)
        if rj.source == "careers" and not category:
            category = "Banking"
        if rj.source in {"topjobs", "itpro", "xpress"} and not category:
            category = "IT"
        if not category:
            continue
        existing = db.query(Job).filter(Job.url == rj.url).first()
        if existing:
            # A previous scan may have been interrupted after saving the card but
            # before fetching its description. Retry those missing details.
            if needs_job_details(existing) and not (
                existing.source == "topjobs" and existing.details_fetched_at
            ):
                try:
                    _enrich_job(db, existing)
                except Exception:
                    db.rollback()
                    log.exception("could not enrich existing job %s", rj.url)
            continue
        details = {
            "description": _html_text(rj.description),
            "requirements": _html_text(rj.requirements),
            "how_to_apply": _html_text(rj.how_to_apply),
            "poster_image_url": "",
        }
        job = Job(title=rj.title, company=rj.company, category=category, source=rj.source,
                  url=rj.url, description=details["description"], requirements=details["requirements"],
                  how_to_apply=details["how_to_apply"], poster_image_url=details["poster_image_url"],
                  details_fetched_at=datetime.utcnow() if details["description"] else None,
                  posted_date=rj.posted_date)
        db.add(job)
        try:
            # Make the job visible before any slow request for its details. This also
            # avoids holding a SQLite write transaction open during network I/O.
            db.commit()
        except Exception:
            db.rollback()
            raise
        added += 1

        # TopJobs placeholder copy is not useful description text, so enrich it
        # immediately just like listings that have no description at all.
        if needs_job_details(job):
            _enrich_job(db, job)
        queue_high_match_job(db, job)
    return added


def run_all_scrapers() -> dict[str, int]:
    results = {}
    db = SessionLocal()
    try:
        for cls in SCRAPERS:
            s = cls()
            started = perf_counter()
            try:
                raw_jobs = s.scrape()
                log.info("scraper %s found %s listings", s.name, len(raw_jobs))
                results[s.name] = save_raw_jobs(db, raw_jobs)
                log.info("scraper %s saved %s new listings in %.1fs",
                         s.name, results[s.name], perf_counter() - started)
            except Exception as e:
                db.rollback()
                log.exception("scraper %s failed: %s", s.name, e)
                results[s.name] = -1
        send_pending_notifications(db)
    finally:
        db.close()
    log.info("scrape finished: %s", results)
    return results
