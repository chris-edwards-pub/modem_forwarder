#!/usr/bin/env python3
"""
Modem Forwarder - Multi-BBS Menu System

A modem-to-telnet bridge with configurable BBS menu and auto-login support.
"""

import argparse
import logging
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import serial

from modem_forwarder.bridge import bridge_session
from modem_forwarder.call_log import CallLog
from modem_forwarder.config import load_config
from modem_forwarder.logging_config import setup_logging
from modem_forwarder.menu import display_menu, get_selection, display_external_menu, display_stats, EXTERNAL_MENU, STATS_MENU
from modem_forwarder.metrics import Metrics
from modem_forwarder.modem import flush_input_buffer, force_hangup, init_modem, wait_for_connect
from modem_forwarder.syncterm import download_syncterm_list
from modem_forwarder.terminal import get_terminal_type, safe_print

logger = logging.getLogger(__name__)

def _get_version():
    """Get version from importlib.metadata, falling back to pyproject.toml."""
    try:
        from importlib.metadata import version as pkg_version
        return pkg_version("modem-forwarder")
    except Exception:
        pass
    try:
        import re
        pyproject = Path(__file__).parent / "pyproject.toml"
        text = pyproject.read_text()
        match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "unknown"


__version__ = _get_version()


def _parse_baud_rate(connect_string):
    """Extract baud rate from CONNECT string (e.g. 'CONNECT 2400/ARQ' -> '2400')."""
    match = re.search(r'CONNECT\s+(\d+)', connect_string, re.IGNORECASE)
    return match.group(1) if match else None


def _get_git_branch():
    """Return the current git branch name, or None if not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def menu_loop(ser, config, gc, external_bbs_list, term_type, call_log=None, metrics=None, session_id=None, local_mode=False):
    """
    Display menu and handle selection in a loop.

    Returns the disconnect reason string, or None for user hangup.
    """
    while True:
        display_menu(
            ser,
            config.bbs_entries,
            gc.welcome_message,
            term_type,
            external_count=len(external_bbs_list),
            has_stats=call_log is not None,
            debug=gc.debug_modem,
        )
        selection = get_selection(
            ser,
            config.bbs_entries,
            term_type,
            has_external=len(external_bbs_list) > 0,
            has_stats=call_log is not None,
            idle_timeout=gc.idle_timeout,
            debug=gc.debug_modem,
        )

        if selection is None:
            # User chose to hang up / quit
            safe_print(ser, "Goodbye!", term_type, debug=gc.debug_modem)
            return "user_hangup"

        if selection == STATS_MENU:
            display_stats(ser, call_log, term_type, debug=gc.debug_modem)
            continue

        if selection == EXTERNAL_MENU:
            # Show external BBS menu
            ext_selection = display_external_menu(
                ser,
                external_bbs_list,
                term_type,
                idle_timeout=gc.idle_timeout,
                debug=gc.debug_modem,
            )
            if ext_selection is None:
                # User chose to go back to main menu
                continue
            selected_bbs = ext_selection
        else:
            selected_bbs = selection

        # Log BBS selection
        protocol = getattr(selected_bbs, 'protocol', 'telnet')
        if call_log and session_id:
            call_log.log_bbs_selection(session_id, selected_bbs.name, protocol)
        if metrics:
            metrics.record_bbs_selection(selected_bbs.name, protocol)

        # Bridge to selected BBS
        disconnect = bridge_session(ser, selected_bbs, gc)
        if disconnect is False:
            # Connection failed, return to menu
            continue
        if local_mode:
            # In local mode, return to menu after session ends
            continue
        return disconnect or "bbs_closed"


def main_loop(config_path: str = "config.yaml", local_mode: bool = False, debug: bool = False) -> None:
    """
    Main application loop.

    Args:
        config_path: Path to configuration file.
        local_mode: If True, use local terminal instead of modem.
        debug: If True, show log output on console.
    """
    # Handle SIGTERM (from systemd stop) the same as SIGINT
    def _handle_sigterm(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _handle_sigterm)

    # Load configuration
    config = load_config(config_path)
    gc = config.global_config

    setup_logging(log_target=gc.log_target, level=gc.log_level, console=debug)

    branch = _get_git_branch()
    version_str = f"v{__version__}"
    if branch and branch != "master":
        version_str += f" ({branch})"
    logger.info(f"Modem Forwarder {version_str} starting...")
    logger.info(f"Baud rate: {gc.default_baudrate}")
    logger.info(f"Loaded {len(config.bbs_entries)} BBS entries")

    # Load external BBS list
    external_bbs_list = download_syncterm_list(gc.external_bbs_url, gc.external_bbs_cache)
    logger.info(f"Loaded {len(external_bbs_list)} external BBS entries")

    # Initialize call logging and metrics
    call_log = CallLog(gc.call_log_db)
    metrics = Metrics(
        url=gc.grafana_cloud_url,
        user=gc.grafana_cloud_user,
        api_key=gc.grafana_cloud_api_key,
    )

    if local_mode:
        from modem_forwarder.local_serial import LocalSerial

        logger.info("Starting in local mode (no modem)")
        try:
            with LocalSerial() as ser:
                term_type = get_terminal_type(ser, debug=gc.debug_modem)
                logger.info(f"Terminal type: {term_type.value}")
                session_id = call_log.start_session(baud_rate="local", terminal_type=term_type.value)
                metrics.record_connect("local", term_type.value)
                disconnect = menu_loop(ser, config, gc, external_bbs_list, term_type,
                                       call_log=call_log, metrics=metrics, session_id=session_id, local_mode=True)
                call_log.end_session(session_id, disconnect or "user_hangup")
                metrics.record_session_end(0, disconnect or "user_hangup")
        except KeyboardInterrupt:
            logger.info("Modem Forwarder shutting down.")
        finally:
            metrics.stop()
            call_log.close()
        return

    try:
        while True:
            try:
                with serial.Serial(
                    gc.modem_port,
                    gc.default_baudrate,
                    timeout=gc.serial_timeout,
                ) as ser:
                    ser.dtr = True
                    ser.rtscts = True
                    ser.xonxoff = False

                    # Ensure clean state before init
                    force_hangup(ser, debug=gc.debug_modem)
                    init_modem(ser, init_sequence=gc.init_sequence, debug=gc.debug_modem)
                    flush_input_buffer(ser, debug=gc.debug_modem)

                    # Wait for incoming call
                    connect_string = wait_for_connect(ser, debug=gc.debug_modem)
                    baud_rate = _parse_baud_rate(connect_string)

                    # Detect or prompt for terminal type
                    term_type = get_terminal_type(ser, debug=gc.debug_modem)
                    logger.info(f"Terminal type: {term_type.value}")

                    # Start call log session
                    session_id = call_log.start_session(baud_rate=baud_rate, terminal_type=term_type.value)
                    metrics.record_connect(baud_rate or "unknown", term_type.value)
                    session_start = time.time()

                    # Show menu and handle selection
                    disconnect = menu_loop(ser, config, gc, external_bbs_list, term_type,
                                           call_log=call_log, metrics=metrics, session_id=session_id)

                    # End call log session
                    duration = int(time.time() - session_start)
                    call_log.end_session(session_id, disconnect or "unknown")
                    metrics.record_session_end(duration, disconnect or "unknown")

                    # Post-session cleanup
                    force_hangup(ser, debug=gc.debug_modem)
                    time.sleep(1)

            except serial.SerialException as e:
                logger.error(f"Serial error: {e}")
                time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Modem Forwarder shutting down.")
    finally:
        metrics.stop()
        call_log.close()
        sys.exit(0)


def cli():
    """CLI entry point for the modem-forwarder console script."""
    parser = argparse.ArgumentParser(description="Modem Forwarder - Multi-BBS Menu System")
    parser.add_argument("--local", action="store_true", help="Local mode: use terminal instead of modem")
    parser.add_argument("--debug", action="store_true", help="Show log output on console")
    parser.add_argument("--config", default="config.yaml", help="Path to configuration file")
    args = parser.parse_args()
    main_loop(config_path=args.config, local_mode=args.local, debug=args.debug)


if __name__ == "__main__":
    cli()
