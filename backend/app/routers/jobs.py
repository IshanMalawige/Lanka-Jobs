import logging
from threading import Lock
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..filters import classify, classify_level, experience_band
from ..models import Job, Status
from ..schemas import JobCreate, JobOut, JobUpdate
from ..scrapers.careers import BANKING_SOURCES
from ..scrapers.runner import run_all_scrapers
from ..services import gmail_parser, skill_gap
from ..services.cv_profile import get_profile
from ..services.telegram_notifier import queue_high_match_job, send_pending_notifications
from ..services.job_details import (
    _html_text,
    needs_job_details,
    refresh_job_details,
    refresh_single_job_details,
)

router = APIRouter(prefix="/api", tags=["jobs"])
log = logging.getLogger(__name__)
_scrape_lock = Lock()
_scrape_state = {"running": False, "results": None, "error": None}
_details_lock = Lock()
_details_state = {"running": False, "results": None, "error": None}
def _matches_position_filters(job: Job, level: str | None, experience: str | None) -> bool:
    if level and classify_level(job.title) != level:
        return False
    if experience and experience_band(
        f"{job.title} {job.description} {job.requirements}"
    ) != experience:
        return False
    return True


def _build_jobs_query(db, q, category, company, status, source):
    query = db.query(Job).filter(Job.source != "careers")
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Job.title.ilike(like), Job.company.ilike(like), Job.description.ilike(like)))
    if category:
        if category == "Interns":
            query = query.filter(or_(
                Job.category.in_(("Interns", "Internship")),
                Job.title.ilike("%internship%"),
                Job.title.ilike("intern"),
                Job.title.ilike("intern %"),
                Job.title.ilike("% intern"),
                Job.title.ilike("% intern %"),
                Job.title.ilike("%trainee%"),
                Job.title.ilike("%graduate%"),
                Job.title.ilike("%associate%"),
            ))
        else:
            query = query.filter(Job.category == category)
    if company:
        query = query.filter(Job.company.ilike(f"%{company}%"))
    if status:
        query = query.filter(Job.status == status)
    if source:
        query = query.filter(Job.source == source)
    return query


@router.get("/banking/sources")
def banking_sources():
    """Official career pages monitored by the banking job collector."""
    return BANKING_SOURCES


@router.get("/jobs/count")
def count_jobs(
    q: str | None = None, category: str | None = None, company: str | None = None,
    status: Status | None = None, source: str | None = None,
    level: Literal["junior", "senior"] | None = None,
    experience: Literal["0-1", "2-3", "4-5", "6+", "unspecified"] | None = None,
    db: Session = Depends(get_db),
):
    query = _build_jobs_query(db, q, category, company, status, source)
    if level or experience:
        return {
            "total": sum(
                1 for job in query.all()
                if _matches_position_filters(job, level, experience)
            )
        }
    return {"total": query.count()}


def _run_scrape():
    try:
        results = run_all_scrapers()
        with _scrape_lock:
            _scrape_state["results"] = results
    except Exception as exc:
        log.exception("scrape failed")
        with _scrape_lock:
            _scrape_state["error"] = str(exc)
    finally:
        with _scrape_lock:
            _scrape_state["running"] = False


def _run_details_refresh(force: bool = False):
    db = SessionLocal()
    try:
        results = refresh_job_details(db, force=force)
        with _details_lock:
            _details_state["results"] = results
    except Exception as exc:
        log.exception("job detail refresh failed")
        db.rollback()
        with _details_lock:
            _details_state["error"] = str(exc)
    finally:
        db.close()
        with _details_lock:
            _details_state["running"] = False


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    q: str | None = None, category: str | None = None, company: str | None = None,
    status: Status | None = None, source: str | None = None,
    level: Literal["junior", "senior"] | None = None,
    experience: Literal["0-1", "2-3", "4-5", "6+", "unspecified"] | None = None,
    sort: str = "new", limit: int = Query(300, ge=1, le=500),
    offset: int = Query(0, ge=0), include_match: bool = True,
    db: Session = Depends(get_db),
):
    query = _build_jobs_query(db, q, category, company, status, source)
    if sort == "company":
        query = query.order_by(func.lower(Job.company).asc(), Job.id.desc())
    elif sort == "match":
        jobs = query.order_by(Job.created_at.desc(), Job.id.desc()).all()
        jobs = [job for job in jobs if _matches_position_filters(job, level, experience)]
        profile = get_profile()
        cv_skills = profile["skills"] if profile else None
        matched_jobs = [
            {
                **JobOut.model_validate(job).model_dump(),
                "skill_match": skill_gap.analyze_job(job, user_skills=cv_skills),
            }
            for job in jobs
        ]
        matched_jobs.sort(
            key=lambda job: (
                job["skill_match"]["match_percent"] is not None,
                job["skill_match"]["match_percent"] if job["skill_match"]["match_percent"] is not None else -1,
                job["created_at"],
                job["id"],
            ),
            reverse=True,
        )
        return matched_jobs[offset:offset + limit]
    else:
        query = query.order_by(Job.created_at.desc(), Job.id.desc())
    if level or experience:
        jobs = query.all()
        jobs = [job for job in jobs if _matches_position_filters(job, level, experience)]
        jobs = jobs[offset:offset + limit]
    else:
        jobs = query.offset(offset).limit(limit).all()
    if not include_match:
        return jobs

    profile = get_profile()
    cv_skills = profile["skills"] if profile else None
    return [
        {
            **JobOut.model_validate(job).model_dump(),
            "skill_match": skill_gap.analyze_job(job, user_skills=cv_skills),
        }
        for job in jobs
    ]


@router.post("/jobs", response_model=JobOut)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    """Used by the browser extension. Manual saves are always kept: if the title
    doesn't match a target role the category is 'Other'."""
    existing = db.query(Job).filter(Job.url == payload.url).first()
    if existing:
        return existing
    job_data = payload.model_dump()
    for field in ("description", "requirements", "how_to_apply"):
        job_data[field] = _html_text(job_data[field])
    job = Job(**job_data, category=classify(payload.title) or "Other")
    db.add(job)
    db.commit()
    db.refresh(job)
    queue_high_match_job(db, job)
    send_pending_notifications(db)
    return job


@router.patch("/jobs/{job_id}", response_model=JobOut)
def update_job(job_id: int, payload: JobUpdate, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if payload.status is not None:
        job.status = payload.status
    if payload.notes is not None:
        job.notes = payload.notes
    db.commit()
    db.refresh(job)
    return job


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    db.delete(job)
    db.commit()
    return {"ok": True}


@router.get("/jobs/{job_id}/skill-gap")
def job_skill_gap(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    profile = get_profile()
    cv_skills = profile["skills"] if profile else None
    return skill_gap.analyze_job(job, user_skills=cv_skills)


@router.post("/scrape")
def trigger_scrape(bg: BackgroundTasks):
    with _scrape_lock:
        if _scrape_state["running"]:
            return {"started": False}
        _scrape_state.update(running=True, results=None, error=None)
    bg.add_task(_run_scrape)
    return {"started": True}


@router.post("/jobs/details/refresh")
def trigger_job_details_refresh(bg: BackgroundTasks, force: bool = False):
    with _details_lock:
        if _details_state["running"]:
            return {"started": False}
        _details_state.update(running=True, results=None, error=None)
    bg.add_task(_run_details_refresh, force)
    return {"started": True}


@router.post("/jobs/{job_id}/details/refresh", response_model=JobOut)
def refresh_one_job_details(job_id: int, force: bool = Query(False), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if force or needs_job_details(job):
        refresh_single_job_details(db, job, force=force)
    if needs_job_details(job):
        raise HTTPException(502, "Could not fetch the full job details from the source.")
    return job


@router.get("/jobs/details/refresh/status")
def job_details_refresh_status():
    with _details_lock:
        return dict(_details_state)


@router.get("/scrape/status")
def scrape_status():
    with _scrape_lock:
        return dict(_scrape_state)


@router.post("/gmail/sync")
def trigger_gmail_sync():
    try:
        return {"updated": gmail_parser.sync_gmail()}
    except Exception as e:
        raise HTTPException(500, f"Gmail sync failed: {e}")


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    out = {s.value: 0 for s in Status}
    for (status,) in db.query(Job.status).filter(Job.source != "careers").all():
        out[status.value] += 1
    out["banking_jobs"] = 0
    return out
