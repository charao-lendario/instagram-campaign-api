"""Pipeline concurrency lock using threading.Lock.

Story 1.7 AC3: Prevents concurrent pipeline executions.
Uses a non-blocking acquire -- if the lock is already held,
the caller gets False and can skip or return 409.
"""

from __future__ import annotations

import threading
from uuid import UUID

_pipeline_lock = threading.Lock()
_current_run_id: UUID | None = None


def acquire_pipeline_lock(run_id: UUID) -> bool:
    """Try to acquire the pipeline lock for the given run.

    Returns True if the lock was acquired, False if already held.
    Uses non-blocking acquire (AC3b).
    """
    global _current_run_id
    if _pipeline_lock.acquire(blocking=False):
        _current_run_id = run_id
        return True
    return False


def release_pipeline_lock() -> None:
    """Release the pipeline lock.

    Safe to call even if the lock is not held (AC3c: always
    released in finally).
    """
    global _current_run_id
    _current_run_id = None
    try:
        _pipeline_lock.release()
    except RuntimeError:
        pass  # Already released


def get_current_run_id() -> UUID | None:
    """Return the run_id of the currently executing pipeline, or None."""
    return _current_run_id


def is_pipeline_running() -> bool:
    """Check if a pipeline is currently running."""
    return _current_run_id is not None
