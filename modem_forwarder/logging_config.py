"""Logging configuration for Modem Forwarder."""

import logging
import sys
from pathlib import Path


def setup_logging(log_file: str = "modem_forwarder.log", level: str = "INFO") -> None:
    """
    Configure logging to file and console.

    Args:
        log_file: Path to log file.
        level: Log level (DEBUG, INFO, WARNING, ERROR).
    """
    # Convert level string to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers
    root_logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logging.info(f"Logging initialized: level={level}, file={log_file}")
