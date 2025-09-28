"""Minimal structured logging helper.

Provides a lightweight wrapper around print() to emit key=value pairs with a
timestamp and level. Avoids pulling in the stdlib logging complexity for this
early-stage project while enabling easier log parsing.

Usage:
    from .logging_utils import log
    log.info(event="server_start", port=5000)

All non-str key/value values are repr()'d. Reserved keys: level, ts.
"""

from __future__ import annotations

import json
import os
import sys
import time

LEVELS = {"debug": 10, "info": 20, "warn": 30, "error": 40}
CURRENT_LEVEL = LEVELS.get(os.getenv("ADVENTURE_LOG_LEVEL", "info"), 20)
JSON_MODE = os.getenv("ADVENTURE_LOG_JSON", "0") in ("1", "true", "TRUE", "yes", "on")


def _format(level: str, **fields):
    if JSON_MODE:
        rec = {k: v for k, v in fields.items() if v is not None}
        rec["level"] = level
        rec["ts"] = int(time.time())
        try:
            return json.dumps(rec, separators=(",", ":"))
        except Exception:
            return json.dumps({"level": level, "ts": int(time.time()), "error": "json_encode_failed"})
    parts = [f"level={level}", f"ts={int(time.time())}"]
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, (int, float)):
            parts.append(f"{k}={v}")
        else:
            s = str(v).replace(" ", "_")
            parts.append(f"{k}={s}")
    return " ".join(parts)


class _Logger:
    def __init__(self, name: str | None = None):
        self.name = name or "adventure"

    def _log(self, lvl: str, threshold: int, **fields):
        if LEVELS[lvl] < CURRENT_LEVEL:
            return
        if "logger" not in fields:
            fields["logger"] = self.name
        print(_format(lvl, **fields), file=sys.stdout if lvl != "error" else sys.stderr)

    def debug(self, **fields):
        self._log("debug", 10, **fields)

    def info(self, **fields):
        self._log("info", 20, **fields)

    def warn(self, **fields):
        self._log("warn", 30, **fields)

    def error(self, **fields):
        self._log("error", 40, **fields)


_LOGGER_CACHE = {}


def get_logger(name: str):
    if name not in _LOGGER_CACHE:
        _LOGGER_CACHE[name] = _Logger(name)
    return _LOGGER_CACHE[name]


log = get_logger("adventure")
