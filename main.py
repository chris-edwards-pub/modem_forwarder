#!/usr/bin/env python3
"""
Modem Forwarder - Multi-BBS Menu System

A modem-to-telnet bridge with configurable BBS menu and auto-login support.
"""

import argparse
import logging
import sys
import time

import serial

from modem_forwarder.bridge import bridge_session
from modem_forwarder.config import load_config
from modem_forwarder.logging_config import setup_logging
from modem_forwarder.menu import display_menu, get_selection, display_external_menu, EXTERNAL_MENU
from modem_forwarder.modem import force_hangup, init_modem, wait_for_connect
from modem_forwarder.syncterm import download_syncterm_list
from modem_forwarder.terminal import get_terminal_type, safe_print

logger = logging.getLogger(__name__)


def menu_loop(ser, config, gc, external_bbs_list, term_type, local_mode=False):
    """
    Display menu and handle selection in a loop.

    Returns when the user chooses to disconnect or the session ends.
    """
    while True:
        display_menu(
            ser,
            config.bbs_entries,
            gc.welcome_message,
            term_type,
            external_count=len(external_bbs_list),
            debug=gc.debug_modem,
        )
        selection = get_selection(
            ser,
            config.bbs_entries,
            term_type,
            has_external=len(external_bbs_list) > 0,
            debug=gc.debug_modem,
        )

        if selection is None:
            # User chose to hang up / quit
            safe_print(ser, "Goodbye!", term_type, debug=gc.debug_modem)
            return

        if selection == EXTERNAL_MENU:
            # Show external BBS menu
            ext_selection = display_external_menu(
                ser,
                external_bbs_list,
                term_type,
                debug=gc.debug_modem,
            )
            if ext_selection is None:
                # User chose to go back to main menu
                continue
            selected_bbs = ext_selection
        else:
            selected_bbs = selection

        # Bridge to selected BBS
        result = bridge_session(ser, selected_bbs, gc)
        if result is False:
            # Connection failed, return to menu
            continue
        if local_mode:
            # In local mode, return to menu after session ends
            continue
        return


def main_loop(config_path: str = "config.yaml", local_mode: bool = False, debug: bool = False) -> None:
    """
    Main application loop.

    Args:
        config_path: Path to configuration file.
        local_mode: If True, use local terminal instead of modem.
        debug: If True, show log output on console.
    """
    # Load configuration
    config = load_config(config_path)
    gc = config.global_config

    # In local mode, suppress console logging unless --debug is passed
    show_console = not local_mode or debug
    setup_logging(log_file=gc.log_file, level=gc.log_level, console=show_console)

    logger.info("Modem Forwarder starting...")
    logger.info(f"Loaded {len(config.bbs_entries)} BBS entries")

    # Load external BBS list
    external_bbs_list = download_syncterm_list(gc.external_bbs_url, gc.external_bbs_cache)
    logger.info(f"Loaded {len(external_bbs_list)} external BBS entries")

    if local_mode:
        from modem_forwarder.local_serial import LocalSerial

        logger.info("Starting in local mode (no modem)")
        try:
            with LocalSerial() as ser:
                term_type = get_terminal_type(ser, debug=gc.debug_modem)
                logger.info(f"Terminal type: {term_type.value}")
                menu_loop(ser, config, gc, external_bbs_list, term_type, local_mode=True)
        except KeyboardInterrupt:
            logger.info("Interrupted, exiting.")
        return

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

                # Show menu and handle selection
                menu_loop(ser, config, gc, external_bbs_list, term_type)

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
    parser = argparse.ArgumentParser(description="Modem Forwarder - Multi-BBS Menu System")
    parser.add_argument("--local", action="store_true", help="Local mode: use terminal instead of modem")
    parser.add_argument("--debug", action="store_true", help="Show log output on console")
    parser.add_argument("--config", default="config.yaml", help="Path to configuration file")
    args = parser.parse_args()
    main_loop(config_path=args.config, local_mode=args.local, debug=args.debug)
