from celery import Celery

from app.config import settings

celery_app = Celery(
    "jobseeker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "app.tasks.resume_tasks.*": {"queue": "parsing"},
        "app.tasks.job_tasks.*": {"queue": "scraping"},
        "app.tasks.matching_tasks.*": {"queue": "ai"},
        "app.tasks.tailoring_tasks.*": {"queue": "ai"},
        "app.tasks.application_tasks.*": {"queue": "applying"},
    },
    task_default_queue="default",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

celery_app.conf.imports = [
    "app.tasks.resume_tasks",
    "app.tasks.job_tasks",
    "app.tasks.tailoring_tasks",
    "app.tasks.application_tasks",
]
