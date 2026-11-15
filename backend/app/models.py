import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Status(str, enum.Enum):
    saved = "saved"
    viewed = "viewed"
    applied = "applied"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("url", name="uq_job_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    company: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(60), index=True)
    source: Mapped[str] = mapped_column(String(60), default="manual")
    url: Mapped[str] = mapped_column(String(1000))
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[str] = mapped_column(Text, default="")
    how_to_apply: Mapped[str] = mapped_column(Text, default="")
    poster_image_url: Mapped[str] = mapped_column(Text, default="")
    details_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    posted_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.saved, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tracked_emails: Mapped[list["TrackedEmail"]] = relationship(back_populates="job", cascade="all, delete-orphan")


class TrackedEmail(Base):
    """An outbound email carrying a tracking pixel."""
    __tablename__ = "tracked_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(40), unique=True, default=lambda: uuid.uuid4().hex)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    recipient: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    first_opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    job: Mapped[Job] = relationship(back_populates="tracked_emails")


class TelegramNotification(Base):
    __tablename__ = "telegram_notifications"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    match_percent: Mapped[int] = mapped_column(Integer)
    estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
