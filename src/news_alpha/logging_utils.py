from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class LogConfig:
    level: str = "INFO"
    json: bool = False
    file: Optional[str] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def configure_logger(cfg: LogConfig) -> logging.Logger:
    """Configure a dedicated NEWS-ALPHA logger.

    The logger is intentionally isolated (no propagation) to reduce the risk of
    interfering with SENTINEL-ALPHA core logging.

    In JSON mode, each emitted line is a JSON object; otherwise, it is a compact
    key=value format.
    """

    logger = logging.getLogger("news_alpha")
    logger.setLevel(getattr(logging, cfg.level.upper(), logging.INFO))
    logger.propagate = False

    # Reset handlers for idempotent configuration in unit tests.
    for h in list(logger.handlers):
        logger.removeHandler(h)

    fmt = logging.Formatter("%(message)s")

    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(logger.level)
    logger.addHandler(sh)

    if cfg.file:
        # Be resilient: create parent directories for the log file path.
        # This prevents surprising failures when users pass paths like "runs/news_alpha.log"
        # without creating the directory first.
        parent = os.path.dirname(os.path.abspath(cfg.file))
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
        fh = logging.FileHandler(cfg.file, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.setLevel(logger.level)
        logger.addHandler(fh)

    # Attach config flags for log_event
    logger._news_alpha_json = bool(cfg.json)  # type: ignore[attr-defined]

    return logger


def log_event(logger: logging.Logger, event: str, *, level: str = "INFO", **fields: Any) -> None:
    """Emit a structured event.

    - event: stable event code (e.g., NEWS_ALPHA_START)
    - fields: structured key-value context (run_id, counts, decisions, ...)

    NOTE: Keep fields small and deterministic; avoid dumping large text blobs.
    """

    payload: Dict[str, Any] = {
        "ts": _utc_now_iso(),
        "event": event,
        **{k: v for k, v in fields.items() if v is not None},
    }

    is_json = bool(getattr(logger, "_news_alpha_json", False))
    if is_json:
        msg = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    else:
        # Compact, deterministic ordering.
        parts = [f"ts={payload['ts']}", f"event={event}"]
        for k in sorted(payload.keys()):
            if k in ("ts", "event"):
                continue
            parts.append(f"{k}={payload[k]}")
        msg = " ".join(parts)

    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn(msg)
