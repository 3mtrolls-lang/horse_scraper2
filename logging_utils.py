"""
logging_utils.py - Logging configuration using Rich for pretty console output
and a rotating file handler for persistent logs.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

try:
    from rich.logging import RichHandler
    from rich.console import Console
    HAS_RICH = True
    _console = Console()
except ImportError:
    HAS_RICH = False
    _console = None

from config import LOGS_DIR


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configure the root 'horse_scraper' logger with:
      - Rich console handler (pretty, coloured)
      - Rotating file handler (plain text)

    Returns the root logger.
    """
    logger = logging.getLogger("horse_scraper")
    logger.setLevel(level)

    # Avoid adding duplicate handlers on repeated calls (e.g. in Colab)
    if logger.handlers:
        return logger

    # ── Console handler ────────────────────────────────────────────
    if HAS_RICH:
        console_handler = RichHandler(
            console=_console,
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
        )
        console_handler.setLevel(level)
        console_fmt = logging.Formatter("%(message)s", datefmt="[%X]")
        console_handler.setFormatter(console_fmt)
    else:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_fmt = logging.Formatter(
            "[%(asctime)s] %(levelname)s  %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_fmt)

    logger.addHandler(console_handler)

    # ── File handler ───────────────────────────────────────────────
    log_filename = os.path.join(
        LOGS_DIR,
        f"horse_scraper_{datetime.now().strftime('%Y%m%d')}.log",
    )
    file_handler = RotatingFileHandler(
        log_filename,
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)
    logger.addHandler(file_handler)

    logger.info("Logging initialised → %s", log_filename)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the horse_scraper namespace."""
    return logging.getLogger(f"horse_scraper.{name}")
