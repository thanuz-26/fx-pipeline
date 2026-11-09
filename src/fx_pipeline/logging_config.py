"""Logging setup: messages go to the console and to a log file."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def setup_logging(log_file: str = "logs/pipeline.log", level: int = logging.INFO) -> None:
    """Send log messages to the console and to a file.

    Safe to call more than once: if logging is already configured, it does
    nothing, so messages are never printed twice.

    Args:
        log_file: Path of the log file (its folder is created if missing).
        level: Lowest level to record, e.g. logging.INFO.
    """
    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)