from __future__ import annotations

import logging
from pathlib import Path


_LOGGERS: set[str] = set()


def configure_logging(logs_dir: Path, name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if name in _LOGGERS:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(logs_dir / f"{name}.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    _LOGGERS.add(name)
    return logger
