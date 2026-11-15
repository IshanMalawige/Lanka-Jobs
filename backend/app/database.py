from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def migrate_schema():
    """Add job detail fields to existing databases without replacing user data."""
    columns = {column["name"] for column in inspect(engine).get_columns("jobs")}
    notification_columns = {
        column["name"] for column in inspect(engine).get_columns("telegram_notifications")
    }
    additions = {
        "requirements": "TEXT NOT NULL DEFAULT ''",
        "how_to_apply": "TEXT NOT NULL DEFAULT ''",
        "poster_image_url": "TEXT NOT NULL DEFAULT ''",
        "details_fetched_at": "TIMESTAMP NULL",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE jobs ADD COLUMN {name} {definition}"))
        connection.execute(text(
            "UPDATE jobs SET category = 'Interns' "
            "WHERE lower(category) IN ('internship', 'interns') "
            "OR (source = 'careers' AND (lower(title) LIKE '%internship%' "
            "OR lower(title) LIKE '%trainee%' OR lower(title) LIKE '%graduate%' "
            "OR lower(title) LIKE '%associate%'))"
        ))
        if notification_columns and "estimated" not in notification_columns:
            connection.execute(
                text("ALTER TABLE telegram_notifications ADD COLUMN estimated BOOLEAN NOT NULL DEFAULT FALSE")
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
