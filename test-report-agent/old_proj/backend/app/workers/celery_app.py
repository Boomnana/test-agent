from celery import Celery
from app.core.config import settings

celery_app = Celery("test_report_agent", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "process_job_pipeline": {"queue": "q_orch"},
        # Future tasks can be routed here
        # "app.workers.tasks.ingest_task": {"queue": "q_io"},
        # "app.workers.tasks.llm_task": {"queue": "q_llm"},
    }
)

# Load tasks
celery_app.autodiscover_tasks(["app.workers"])
