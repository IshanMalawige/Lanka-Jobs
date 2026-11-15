from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job, TrackedEmail
from ..schemas import TrackedEmailCreate, TrackedEmailOut
from ..services.tracking import PIXEL_GIF, to_out

router = APIRouter(prefix="/api", tags=["tracking"])


@router.post("/track", response_model=TrackedEmailOut)
def create_tracker(payload: TrackedEmailCreate, db: Session = Depends(get_db)):
    if not db.get(Job, payload.job_id):
        raise HTTPException(404, "Job not found")
    t = TrackedEmail(job_id=payload.job_id, recipient=payload.recipient)
    db.add(t)
    db.commit()
    db.refresh(t)
    return to_out(t)


@router.get("/track/{token}.gif")
def pixel(token: str, db: Session = Depends(get_db)):
    t = db.query(TrackedEmail).filter(TrackedEmail.token == token).first()
    if t:
        now = datetime.utcnow()
        t.open_count += 1
        t.first_opened_at = t.first_opened_at or now
        t.last_opened_at = now
        db.commit()
    return Response(PIXEL_GIF, media_type="image/gif",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@router.get("/track", response_model=list[TrackedEmailOut])
def list_trackers(job_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(TrackedEmail)
    if job_id:
        q = q.filter(TrackedEmail.job_id == job_id)
    return [to_out(t) for t in q.order_by(TrackedEmail.created_at.desc()).all()]
