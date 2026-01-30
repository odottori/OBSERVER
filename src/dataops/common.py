from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import yaml


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_run_id(prefix: str = "DATAOPS") -> str:
    """Generate a deterministic-enough run id for operational logging."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short = uuid.uuid4().hex[:10]
    p = str(prefix).strip().upper()
    return f"{p}_{ts}_{short}"


def truthy_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "y", "on"}


def read_yaml(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def write_yaml(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f, sort_keys=False, allow_unicode=True)


@contextmanager
def timing() -> Iterator[callable[[], int]]:
    start = time.time()

    def elapsed_ms() -> int:
        return int((time.time() - start) * 1000)

    yield elapsed_ms
