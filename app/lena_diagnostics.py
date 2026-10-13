"""Persistent best-effort crash diagnostics without image data."""

import faulthandler
import json
import os
import sys
import threading
import time
import traceback
from lena_config import HOME

_stream = None
_lock = threading.Lock()


def record(event, **fields):
    if _stream is None:
        return
    try:
        with _lock:
            _stream.write(
                json.dumps(
                    {"time": time.time(), "pid": os.getpid(), "event": event, **fields},
                    ensure_ascii=False,
                )
                + "\n"
            )
            _stream.flush()
    except (OSError, ValueError):
        pass


def exception(kind, value, tb):
    record("exception", traceback="".join(traceback.format_exception(kind, value, tb)))


def install(worker=False):
    global _stream
    if _stream is not None:
        return
    try:
        HOME.mkdir(parents=True, exist_ok=True)
        path = HOME / ("crash-worker.log" if worker else "crash-ui.log")
        if path.exists() and path.stat().st_size > 2_000_000:
            path.replace(path.with_suffix(".previous.log"))
        _stream = path.open("a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=_stream, all_threads=True)
    except (OSError, RuntimeError, ValueError):
        return
    sys.excepthook = exception
    threading.excepthook = lambda args: exception(
        args.exc_type, args.exc_value, args.exc_traceback
    )
    record("start", worker=worker, frozen=bool(getattr(sys, "frozen", False)))
