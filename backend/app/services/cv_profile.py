"""Store only the extracted skills from a local CV, never the original PDF."""

import json
from io import BytesIO
from pathlib import Path

from .skill_gap import extract_resume_skills

_PROFILE_PATH = Path(__file__).resolve().parents[2] / "data" / "cv_profile.json"


def get_profile() -> dict | None:
    try:
        profile = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
        skills = profile.get("skills")
        if isinstance(skills, list) and skills:
            return {"uploaded": True, "skills": [str(skill) for skill in skills]}
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return None


def extract_profile(content: bytes) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    if reader.is_encrypted:
        raise ValueError("This PDF is password-protected. Please upload an unlocked copy.")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    skills = extract_resume_skills(text)
    if not skills:
        raise ValueError("I could not detect supported skills in this PDF. Try a text-based PDF CV.")
    return skills


def save_profile(skills: list[str]) -> dict:
    _PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = _PROFILE_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps({"skills": skills}, indent=2), encoding="utf-8")
    temporary_path.replace(_PROFILE_PATH)
    return {"uploaded": True, "skills": skills}
