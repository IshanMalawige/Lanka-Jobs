import base64
import binascii

from fastapi import APIRouter, HTTPException

from ..schemas import CVUpload
from ..services.cv_profile import extract_profile, get_profile, save_profile

router = APIRouter(prefix="/api", tags=["profile"])
_MAX_CV_BYTES = 10 * 1024 * 1024


@router.get("/cv")
def read_cv_profile():
    return get_profile() or {"uploaded": False, "skills": []}


@router.put("/cv")
def upload_cv(payload: CVUpload):
    if not payload.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Upload a PDF CV.")
    try:
        content = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "The uploaded file could not be decoded.") from None
    if len(content) > _MAX_CV_BYTES:
        raise HTTPException(413, "The CV must be 10 MB or smaller.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(400, "The selected file is not a valid PDF.")

    try:
        skills = extract_profile(content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception:
        raise HTTPException(422, "Could not read this PDF. Please try another text-based PDF CV.") from None
    return save_profile(skills)
