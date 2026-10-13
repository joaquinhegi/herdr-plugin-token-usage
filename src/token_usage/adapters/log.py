"""Rotating file log that can only carry event names, ints and safe tokens."""

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def make_logger(directory: Path, name: str = "token_usage") -> logging.Logger:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = RotatingFileHandler(directory / "token-usage.log", maxBytes=256 * 1024, backupCount=1)
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    return logger


def close_logger(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


def _safe(value: object) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str) and _TOKEN.match(value):
        return value
    return "?"


def log_event(logger: logging.Logger, event: str, **fields: object) -> None:
    parts = [_safe(event)] + [f"{_safe(k)}={_safe(v)}" for k, v in fields.items()]
    logger.info(" ".join(parts))


def log_exception(logger: logging.Logger, event: str, exc: BaseException) -> None:
    log_event(logger, event, error=type(exc).__name__)
