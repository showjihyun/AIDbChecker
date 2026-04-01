# Spec: AG-001, MVP-COLLECT-001, MVP-AI-001
"""Celery application definition with beat schedule for metric collection and baseline training."""

from celery import Celery
from celery.schedules import crontab, schedule

from app.config import settings

celery_app = Celery(
    "neuraldb",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Task routing
    task_routes={
        "app.tasks.collect.*": {"queue": "collect"},
        "app.tasks.alert.*": {"queue": "alert"},
        "app.tasks.analyze.*": {"queue": "analyze"},
    },
    # Beat schedule: hot (1s), warm (10s), cold (60s), ash (1s)
    beat_schedule={
        "collect-hot-metrics": {
            "task": "app.tasks.collect.collect_hot_metrics",
            "schedule": schedule(run_every=1.0),
            "options": {"queue": "collect"},
        },
        "collect-warm-metrics": {
            "task": "app.tasks.collect.collect_warm_metrics",
            "schedule": schedule(run_every=10.0),
            "options": {"queue": "collect"},
        },
        "collect-cold-metrics": {
            "task": "app.tasks.collect.collect_cold_metrics",
            "schedule": schedule(run_every=60.0),
            "options": {"queue": "collect"},
        },
        "collect-ash-samples": {
            "task": "app.tasks.collect.collect_ash_samples",
            "schedule": schedule(run_every=1.0),
            "options": {"queue": "collect"},
        },
        # Spec: MVP-AI-001 -- retrain baselines every 6 hours
        "retrain-baselines": {
            "task": "app.tasks.analyze.retrain_baselines",
            "schedule": crontab(minute=0, hour="*/6"),
            "options": {"queue": "analyze"},
        },
        # Spec: FS-SCHEMA-001 -- detect DDL changes every 60 seconds
        "detect-schema-changes": {
            "task": "app.tasks.schema.detect_schema_changes",
            "schedule": schedule(run_every=60.0),
            "options": {"queue": "collect"},
        },
        # Spec: FS-DBA-003 -- Proactive Agent schedules
        "proactive-quick-check": {
            "task": "proactive_quick_check",
            "schedule": crontab(minute="*/30"),
            "options": {"queue": "analyze"},
        },
        "proactive-deep-analysis": {
            "task": "proactive_deep_analysis",
            "schedule": crontab(minute=0, hour="*/6"),
            "options": {"queue": "analyze"},
        },
        "proactive-morning-report": {
            "task": "proactive_morning_report",
            "schedule": crontab(minute=0, hour=9),
            "options": {"queue": "analyze"},
        },
        # Spec: FS-AI-REPORT-001 — DBA periodic reports
        "daily-dba-report": {
            "task": "app.tasks.reports.generate_dba_report",
            "schedule": crontab(minute=0, hour=9),
            "args": ("daily",),
            "options": {"queue": "analyze"},
        },
        "weekly-dba-report": {
            "task": "app.tasks.reports.generate_dba_report",
            "schedule": crontab(minute=0, hour=9, day_of_week=1),
            "args": ("weekly",),
            "options": {"queue": "analyze"},
        },
        "monthly-dba-report": {
            "task": "app.tasks.reports.generate_dba_report",
            "schedule": crontab(minute=0, hour=9, day_of_month=1),
            "args": ("monthly",),
            "options": {"queue": "analyze"},
        },
    },
)

# Explicitly include all task modules so Celery workers can find them
celery_app.conf.include = [
    "app.tasks.collect",
    "app.tasks.alert",
    "app.tasks.analyze",
    "app.tasks.schema",
    "app.tasks.proactive",
    "app.tasks.reports",
]
