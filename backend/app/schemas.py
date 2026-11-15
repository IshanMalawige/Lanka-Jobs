from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from .models import Status


class JobCreate(BaseModel):
    title: str
    company: str = ""
    url: str
    source: str = "extension"
    description: str = ""
    requirements: str = ""
    how_to_apply: str = ""
    posted_date: datetime | None = None
    notes: str = ""


class JobUpdate(BaseModel):
    status: Status | None = None
    notes: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    company: str
    category: str
    source: str
    url: str
    description: str
    requirements: str
    how_to_apply: str
    poster_image_url: str
    posted_date: datetime | None
    status: Status
    notes: str
    created_at: datetime
    skill_match: dict | None = None


class CVUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(min_length=1, max_length=14_000_000)


class TrackedEmailCreate(BaseModel):
    job_id: int
    recipient: str = ""


class TrackedEmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    token: str
    job_id: int
    recipient: str
    open_count: int
    first_opened_at: datetime | None
    last_opened_at: datetime | None
    pixel_url: str = ""
    html_snippet: str = ""
