"""Structured logging configuration for Shabana Smart Sort."""
import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(log_dir: Optional[Path] = None, log_level: int = logging.INFO) -> logging.Logger:
    """Configures structured console and file logging."""
    logger = logging.getLogger("ShabanaSmartSort")
    logger.setLevel(log_level)

    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(funcName)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)

    # File handler if directory specified
    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_path = log_dir / "smart_sort.log"
            file_handler = logging.FileHandler(file_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not initialize file logger at {log_dir}: {e}")

    return logger
