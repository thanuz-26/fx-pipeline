"""Tests for logging_config.py (log files go to a temporary folder)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from fx_pipeline.logging_config import setup_logging


@contextmanager
def empty_root_logger() -> Iterator[logging.Logger]:
    """Give the test body an empty root logger, then restore the old one.

    This must run INSIDE the test: pytest re-adds its own log handlers just
    before each test body, and setup_logging() does nothing if handlers exist.
    """
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    root.handlers.clear()
    try:
        yield root
    finally:
        for handler in root.handlers:
            handler.close()  # closes the log file (Windows cannot delete open files)
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)


def test_messages_go_to_console_and_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_file = tmp_path / "logs" / "pipeline.log"  # the folder does not exist yet
    with empty_root_logger():
        setup_logging(str(log_file))
        logging.getLogger("fx_pipeline.test").warning("something to see")
        content = log_file.read_text(encoding="utf-8")

    assert "WARNING" in capsys.readouterr().out
    assert "WARNING" in content
    assert "fx_pipeline.test" in content
    assert "something to see" in content


def test_debug_messages_are_hidden_at_info_level(tmp_path: Path) -> None:
    log_file = tmp_path / "pipeline.log"
    with empty_root_logger():
        setup_logging(str(log_file))
        logger = logging.getLogger("fx_pipeline.test")
        logger.debug("hidden detail")
        logger.info("visible news")
        content = log_file.read_text(encoding="utf-8")

    assert "visible news" in content
    assert "hidden detail" not in content


def test_calling_setup_twice_does_not_duplicate_messages(tmp_path: Path) -> None:
    log_file = tmp_path / "pipeline.log"
    with empty_root_logger() as root:
        setup_logging(str(log_file))
        setup_logging(str(log_file))  # the second call must change nothing
        logging.getLogger("fx_pipeline.test").info("only once please")
        content = log_file.read_text(encoding="utf-8")
        handler_count = len(root.handlers)

    assert handler_count == 2  # one for the console, one for the file
    assert content.count("only once please") == 1


def test_existing_configuration_is_left_alone(tmp_path: Path) -> None:
    log_file = tmp_path / "pipeline.log"
    with empty_root_logger() as root:
        root.addHandler(logging.NullHandler())  # someone configured logging already
        setup_logging(str(log_file))
        handler_count = len(root.handlers)

    assert handler_count == 1
    assert not log_file.exists()  # no file was created