#!/usr/bin/env python3
"""
Modem Forwarder - Multi-BBS Menu System

A modem-to-telnet bridge with configurable BBS menu and auto-login support.
"""

import logging
import sys
import time

import serial

from modem_forwarder.bridge import bridge_session
from modem_forwarder.config import load_config
from modem_forwarder.logging_config import setup_logging
from modem_forwarder.menu import display_menu, get_selection
from modem_forwarder.modem import force_hangup, init_modem, modem_print, wait_for_connect
from modem_forwarder.terminal import get_terminal_type, safe_print

logger = logging.getLogger(__name__)


def main_loop(config_path: str = "config.yaml") -> None:
    """
    Main application loop.

    Args:
        config_path: Path to configuration file.
    """
    # Load configuration
    config = load_config(config_path)
    gc = config.global_config

    # Setup logging
    setup_logging(log_file=gc.log_file, level=gc.log_level)

    logger.info("Modem Forwarder starting...")
    logger.info(f"Loaded {len(config.bbs_entries)} BBS entries")

    while True:
        try:
            with serial.Serial(
                gc.modem_port,
                gc.default_baudrate,
                timeout=gc.serial_timeout,
            ) as ser:
                ser.dtr = True
                ser.xonxoff = True

                # Ensure clean state before init
                force_hangup(ser, debug=gc.debug_modem)
                init_modem(ser, init_sequence=gc.init_sequence, debug=gc.debug_modem)

                # Wait for incoming call
                connect_string = wait_for_connect(ser, debug=gc.debug_modem)

                # Detect or prompt for terminal type
                term_type = get_terminal_type(ser, debug=gc.debug_modem)
                logger.info(f"Terminal type: {term_type.value}")

                # Show menu and get selection
                display_menu(
                    ser,
                    config.bbs_entries,
                    gc.welcome_message,
                    term_type,
                    debug=gc.debug_modem,
                )
                selected_bbs = get_selection(
                    ser,
                    config.bbs_entries,
                    term_type,
                    debug=gc.debug_modem,
                )

                if selected_bbs is None:
                    # User chose to hang up
                    safe_print(ser, "Goodbye!", term_type, debug=gc.debug_modem)
                    force_hangup(ser, debug=gc.debug_modem)
                    continue

                # Bridge to selected BBS
                bridge_session(ser, selected_bbs, gc)

                # Post-session cleanup
                force_hangup(ser, debug=gc.debug_modem)
                time.sleep(1)

        except serial.SerialException as e:
            logger.error(f"Serial error: {e}")
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Interrupted, exiting.")
            sys.exit(0)


if __name__ == "__main__":
    main_loop()
