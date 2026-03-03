from celery import Celery

from app.config import settings

celery = Celery("knowledge_arena", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "check-overdue-turns": {
            "task": "app.tasks.arbiter_tasks.check_overdue_turns",
            "schedule": 30.0,
        },
        "detect-gaps": {
            "task": "app.tasks.graph_tasks.detect_gaps",
            "schedule": 3600.0,
        },
        "check-standing-theses": {
            "task": "app.tasks.graph_tasks.check_standing_theses",
            "schedule": 86400.0,
        },
    },
)
