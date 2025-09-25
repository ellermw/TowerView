import os
from celery import Celery
from .config import settings

# Create Celery instance
celery_app = Celery(
    'towerview_worker',
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['worker.tasks']
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'poll-servers': {
        'task': 'worker.tasks.poll_all_servers',
        'schedule': 30.0,  # Every 30 seconds
    },
    'cleanup-old-sessions': {
        'task': 'worker.tasks.cleanup_old_sessions',
        'schedule': 300.0,  # Every 5 minutes
    },
    'update-server-status': {
        'task': 'worker.tasks.update_server_status',
        'schedule': 60.0,  # Every minute
    },
}