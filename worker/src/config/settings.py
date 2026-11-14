"""worker 侧配置（与 backend 共用同一批环境变量）。"""
from __future__ import annotations

import os

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
HEARTBEAT_KEY = "docflow:worker:heartbeat"
HEARTBEAT_INTERVAL_SECONDS = 30
SWEEP_INTERVAL_SECONDS = 600
