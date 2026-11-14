"""worker Celery 应用：消费 docflow.archive_run，beat 负责心跳与投件目录巡检。"""
from __future__ import annotations

from celery import Celery
from celery.schedules import schedule

from worker_src.config.settings import (
    HEARTBEAT_INTERVAL_SECONDS,
    REDIS_URL,
    SWEEP_INTERVAL_SECONDS,
)

celery_app = Celery(
    "docflow-worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "worker_src.tasks.archive_task",
        "worker_src.tasks.heartbeat_task",
        "worker_src.tasks.sweep_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    result_expires=1800,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_acks_late=False,
    broker_transport_options={"socket_connect_timeout": 5, "socket_timeout": 5},
    beat_schedule={
        "worker-heartbeat": {
            "task": "docflow.heartbeat",
            "schedule": schedule(run_every=HEARTBEAT_INTERVAL_SECONDS),
        },
        "drop-sweep": {
            "task": "docflow.drop_sweep",
            "schedule": schedule(run_every=SWEEP_INTERVAL_SECONDS),
        },
    },
)
