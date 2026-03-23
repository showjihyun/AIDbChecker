---
name: gen-celery-task
description: Generate Celery async task definitions for background processing. Creates tasks for metric collection (1s), agent execution, playbook runs, report generation, and scheduled maintenance with proper retry, timeout, and error handling.
argument-hint: "[task-name] [schedule: periodic|on-demand]"
allowed-tools: Read, Write, Glob, Grep, Edit
---

# Generate Celery Task

## Arguments
- Task name: $0
- Schedule type: $1 (default: on-demand)

## Output File
```
backend/app/tasks/{task_name}.py
```

## Template
```python
from celery import shared_task
from celery.utils.log import get_task_logger
from app.config import settings

logger = get_task_logger(__name__)

@shared_task(
    name="{task_name}",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    soft_time_limit=300,
    time_limit=600,
    acks_late=True,
    reject_on_worker_lost=True,
)
def {task_name}(self, instance_id: str, **kwargs):
    """Task description."""
    try:
        logger.info(f"Starting {task_name} for {instance_id}")
        # Business logic here
        result = ...
        logger.info(f"Completed {task_name}: {result}")
        return result
    except Exception as exc:
        logger.error(f"{task_name} failed: {exc}")
        self.retry(exc=exc)
```

## Periodic Task (Celery Beat)
```python
# backend/app/tasks/schedule.py
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'collect-hot-metrics': {
        'task': 'collect_hot_metrics',
        'schedule': 1.0,  # every 1 second
    },
    'collect-warm-metrics': {
        'task': 'collect_warm_metrics',
        'schedule': 10.0,  # every 10 seconds
    },
    'downsample-metrics': {
        'task': 'downsample_metrics',
        'schedule': crontab(minute='*/5'),
    },
    'baseline-update': {
        'task': 'update_baseline',
        'schedule': crontab(hour='*/6'),
    },
}
```

## Task Categories
| Category | Tasks | Schedule |
|----------|-------|----------|
| Collection | collect_hot_metrics, collect_ash, collect_warm_metrics | 1s / 1s / 10s |
| Analysis | detect_anomaly, update_baseline, analyze_query | Event / 6h / On-demand |
| Agent | run_diagnosis, execute_playbook, generate_report | Event / Event / On-demand |
| Maintenance | downsample_metrics, cleanup_old_data, vacuum_tables | 5m / Daily / Weekly |

## Rules
- `acks_late=True` for at-least-once delivery
- `soft_time_limit` for graceful shutdown before hard kill
- Structured logging with correlation ID
- Idempotent tasks (safe to retry)
- Use `self.retry(exc=exc)` with exponential backoff
- Valkey as broker: `CELERY_BROKER_URL = "redis://valkey:6379/0"`
