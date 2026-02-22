"""Structured logging configuration.

Configures the root logger with a structured format including timestamp,
level, and module name.  The log level is controlled by ``settings.LOG_LEVEL``.
"""

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application.

    Sets the root logger level from ``settings.LOG_LEVEL`` and installs a
    ``StreamHandler`` writing to *stdout* with a structured text format.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(log_level)

    # Avoid adding duplicate handlers on repeated calls
    if not root.handlers:
        root.addHandler(handler)
    else:
        root.handlers.clear()
        root.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
