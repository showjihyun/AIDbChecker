# Spec: MVP-DASH-001, MVP-COLLECT-001
"""Demo seed script — creates sample instances, metrics, incidents for demo.

Usage:
    uv run python -m app.db.seed_demo

Creates:
- 3 DB instances (production, staging, development)
- Sample metric snapshots (last 1 hour, 10-second intervals)
- 5 sample incidents (2 critical, 2 warning, 1 resolved)
- 3 baselines
- Default admin user (via seed.py)
"""

import asyncio
import random
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import structlog
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.baseline import Baseline
from app.models.db_instance import DBInstance
from app.models.incident import Incident
from app.models.metric import MetricSample

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Demo instances
# ---------------------------------------------------------------------------

DEMO_INSTANCES = [
    {
        "name": "pg-prod-01",
        "db_type": "postgresql",
        "host": "10.0.1.10",
        "port": 5432,
        "database_name": "production_db",
        "environment": "production",
        "autonomy_level": 1,
        "metadata": {"region": "ap-northeast-2", "team": "platform"},
    },
    {
        "name": "pg-staging-01",
        "db_type": "postgresql",
        "host": "10.0.2.10",
        "port": 5432,
        "database_name": "staging_db",
        "environment": "staging",
        "autonomy_level": 2,
        "metadata": {"region": "ap-northeast-2", "team": "platform"},
    },
    {
        "name": "pg-dev-01",
        "db_type": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database_name": "dev_db",
        "environment": "development",
        "autonomy_level": 0,
        "metadata": {"region": "local", "team": "backend"},
    },
]


async def seed_demo() -> None:
    """Create demo data for all tables."""
    # First, seed admin user
    from app.db.seed import seed_default_admin

    await seed_default_admin()

    async with AsyncSessionLocal() as session:
        # Check if demo data already exists
        stmt = select(DBInstance.id).where(DBInstance.name == "pg-prod-01")
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            logger.info("seed_demo.skip", reason="Demo data already exists")
            return

        now = datetime.now(UTC)
        instance_ids = []

        # ----- Instances -----
        for inst_data in DEMO_INSTANCES:
            inst = DBInstance(
                id=uuid4(),
                **inst_data,
                connection_config={"ssl_mode": "prefer"},
                is_active=True,
            )
            session.add(inst)
            instance_ids.append(inst.id)
            logger.info("seed_demo.instance", name=inst.name, id=str(inst.id))

        await session.flush()

        # ----- Metrics (last 1 hour, every 10 seconds for prod) -----
        prod_id = instance_ids[0]
        metrics_count = 0
        for i in range(360):  # 360 * 10s = 1 hour
            ts = now - timedelta(seconds=(360 - i) * 10)
            cpu = 30 + random.gauss(10, 5)
            mem = 60 + random.gauss(5, 3)
            conn = int(40 + random.gauss(10, 5))
            tps = int(200 + random.gauss(50, 20))

            sample = MetricSample(
                id=uuid4(),
                instance_id=prod_id,
                sampled_at=ts,
                category="hot",
                metrics={
                    "cpu_usage": round(max(0, min(100, cpu)), 1),
                    "memory_usage": round(max(0, min(100, mem)), 1),
                    "active_connections": max(1, conn),
                    "tps": max(0, tps),
                    "buffer_hit_ratio": round(95 + random.uniform(0, 4.9), 2),
                },
            )
            session.add(sample)
            metrics_count += 1

        logger.info("seed_demo.metrics", count=metrics_count, instance="pg-prod-01")

        # ----- Incidents -----
        incidents_data = [
            {
                "instance_id": prod_id,
                "severity": "critical",
                "status": "open",
                "title": "CPU usage exceeded 92% on pg-prod-01",
                "description": "CPU spiked to 92% at 14:30. Baseline normal range: 30-50%.",
                "source": "ai_baseline",
                "metric_type": "cpu_usage",
                "metric_value": 92.3,
                "baseline_value": 40.0,
                "detected_at": now - timedelta(minutes=30),
            },
            {
                "instance_id": prod_id,
                "severity": "warning",
                "status": "acknowledged",
                "title": "Connection pool reaching 80% capacity",
                "description": "Active connections at 160/200. Approaching saturation.",
                "source": "threshold",
                "metric_type": "active_connections",
                "metric_value": 160,
                "baseline_value": 80,
                "detected_at": now - timedelta(hours=2),
            },
            {
                "instance_id": prod_id,
                "severity": "critical",
                "status": "in_progress",
                "title": "Deadlock detected in orders table",
                "description": "2 sessions deadlocked on orders table UPDATE. Auto-detected via pg_stat_activity.",
                "source": "ai_baseline",
                "metric_type": "deadlocks",
                "metric_value": 2,
                "baseline_value": 0,
                "detected_at": now - timedelta(minutes=15),
            },
            {
                "instance_id": instance_ids[1],
                "severity": "warning",
                "status": "open",
                "title": "Replication lag exceeding 5 seconds on pg-staging-01",
                "description": "WAL replay lag at 8.2 seconds. Threshold: 5s.",
                "source": "threshold",
                "metric_type": "replication_lag",
                "metric_value": 8.2,
                "baseline_value": 0.5,
                "detected_at": now - timedelta(hours=1),
            },
            {
                "instance_id": prod_id,
                "severity": "notice",
                "status": "resolved",
                "title": "Sequential scan ratio above 80% on users table",
                "description": "Missing index on users.email caused seq scan. Index created.",
                "source": "ai_baseline",
                "metric_type": "seq_scan_ratio",
                "metric_value": 85.0,
                "baseline_value": 20.0,
                "detected_at": now - timedelta(days=1),
                "resolved_at": now - timedelta(hours=20),
            },
        ]

        for inc_data in incidents_data:
            incident = Incident(id=uuid4(), **inc_data)
            session.add(incident)

        logger.info("seed_demo.incidents", count=len(incidents_data))

        # ----- Baselines -----
        baselines_data = [
            {
                "instance_id": prod_id,
                "metric_type": "cpu_usage",
                "time_bucket": "weekday_business",
                "normal_min": 20.0,
                "normal_max": 55.0,
                "mean": 35.0,
                "stddev": 8.0,
                "model_type": "stl",
                "model_params": {"period": 86400, "seasonal": 7},
                "training_samples": 120960,
                "last_trained_at": now - timedelta(hours=3),
            },
            {
                "instance_id": prod_id,
                "metric_type": "active_connections",
                "time_bucket": "weekday_business",
                "normal_min": 30.0,
                "normal_max": 100.0,
                "mean": 60.0,
                "stddev": 15.0,
                "model_type": "stl",
                "model_params": {"period": 86400},
                "training_samples": 120960,
                "last_trained_at": now - timedelta(hours=3),
            },
            {
                "instance_id": prod_id,
                "metric_type": "tps",
                "time_bucket": "weekday_business",
                "normal_min": 100.0,
                "normal_max": 350.0,
                "mean": 200.0,
                "stddev": 50.0,
                "model_type": "isolation_forest",
                "model_params": {"contamination": 0.05},
                "training_samples": 120960,
                "last_trained_at": now - timedelta(hours=3),
            },
        ]

        for bl_data in baselines_data:
            baseline = Baseline(id=uuid4(), **bl_data, is_active=True)
            session.add(baseline)

        logger.info("seed_demo.baselines", count=len(baselines_data))

        await session.commit()
        logger.info(
            "seed_demo.complete",
            instances=len(DEMO_INSTANCES),
            metrics=metrics_count,
            incidents=len(incidents_data),
            baselines=len(baselines_data),
        )


def main() -> None:
    """Entry point for `uv run python -m app.db.seed_demo`."""
    asyncio.run(seed_demo())
    print("Demo seed complete!")
    print("  - 3 instances (prod/staging/dev)")
    print("  - 360 metric samples (1 hour, 10s interval)")
    print("  - 5 incidents (2 critical, 2 warning, 1 resolved)")
    print("  - 3 baselines (cpu, connections, tps)")
    print("  - 1 admin user (admin@neuraldb.local / change-me-in-production)")


if __name__ == "__main__":
    main()
