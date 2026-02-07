"""Logging configuration for Modem Forwarder."""

import logging
import logging.handlers
import sys


def setup_logging(log_target: str = "syslog", level: str = "INFO", console: bool = False) -> None:
    """
    Configure logging to syslog or file, and optionally console.

    Args:
        log_target: "syslog" for system syslog, or a file path for file logging.
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        console: If True, also log to console (stdout).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    if log_target == "syslog":
        syslog_handler = logging.handlers.SysLogHandler(address="/dev/log")
        syslog_formatter = logging.Formatter(
            "modem-forwarder: [%(levelname)s] %(name)s: %(message)s"
        )
        syslog_handler.setLevel(log_level)
        syslog_handler.setFormatter(syslog_formatter)
        root_logger.addHandler(syslog_handler)
    else:
        file_handler = logging.FileHandler(log_target)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    logging.info(f"Logging initialized: level={level}, target={log_target}")
