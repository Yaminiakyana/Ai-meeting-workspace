from celery import Celery
from celery.app import trace
from celery.signals import worker_init, worker_process_init

from app.core.config import settings


celery_app = Celery(
    "ai_meeting_workspace",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.worker.tasks",
    ],
)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_pool="solo",
)


def _init_celery_tracing():
    """
    Ensure fast_trace_task optimization variables (_localized) are initialized
    in the Celery worker process and child processes (especially on macOS / Python 3.8+
    where multiprocessing uses spawn and leaves _localized empty).
    """
    try:
        trace.setup_worker_optimizations(celery_app)
    except Exception:
        pass


# Initialize tracing immediately upon module import
_init_celery_tracing()


@worker_init.connect
def on_worker_init(**kwargs):
    _init_celery_tracing()


@worker_process_init.connect
def on_worker_process_init(**kwargs):
    _init_celery_tracing()


