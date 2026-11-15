import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401  (register tables)
from .config import settings
from .database import Base, engine, migrate_schema
from .routers import jobs, profile, tracking
from .services import scheduler

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    migrate_schema()
    if settings.enable_scheduler:
        scheduler.start()
    yield
    if scheduler.scheduler.running:
        scheduler.scheduler.shutdown(wait=False)


app = FastAPI(title="LankaJobs - IT Job Aggregator", lifespan=lifespan)


@app.get("/")
def root():
    return {
        "ok": True,
        "message": "LankaJobs API is running",
        "docs": "/docs",
        "jobs": "/api/jobs",
        "health": "/api/health",
    }


origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"chrome-extension://.*",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jobs.router)
app.include_router(profile.router)
app.include_router(tracking.router)


@app.get("/api/health")
def health():
    return {"ok": True}
