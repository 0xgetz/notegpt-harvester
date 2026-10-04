"""Structured logging helpers."""

from __future__ import annotations

import logging
import sys


class _Formatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"

    def __init__(self, color: bool) -> None:
        super().__init__("%(asctime)s %(levelname)-8s %(message)s", "%H:%M:%S")
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if self.color and record.levelname in self.COLORS:
            return f"{self.COLORS[record.levelname]}{text}{self.RESET}"
        return text


def setup_logging(level: str = "INFO", quiet: bool = False) -> logging.Logger:
    """Configure the root logger once and return the package logger."""
    logger = logging.getLogger("notegpt_harvester")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG if not quiet else logging.WARNING)

    if not quiet:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        handler.setFormatter(_Formatter(sys.stderr.isatty()))
        logger.addHandler(handler)
        logger.propagate = False
    return logger


log = logging.getLogger("notegpt_harvester")
