"""Menu display and selection system."""

import logging
from typing import List, Optional

import serial

from .config import BBSEntry
from .modem import modem_getch
from .terminal import TerminalType, safe_print, color_print, Color

logger = logging.getLogger(__name__)


def display_menu(
    ser: serial.Serial,
    bbs_entries: List[BBSEntry],
    welcome_message: str,
    term_type: TerminalType,
    debug: bool = False,
) -> None:
    """
    Display the BBS selection menu to the modem user.

    Args:
        ser: Serial port object.
        bbs_entries: List of available BBS entries.
        welcome_message: Welcome message to display.
        term_type: Terminal type for charset-safe output.
        debug: Enable debug logging.
    """
    logger.info(f"Displaying menu with {len(bbs_entries)} BBS entries")

    safe_print(ser, "", term_type, debug=debug)
    color_print(ser, welcome_message, Color.CYAN, term_type, debug=debug)
    safe_print(ser, "", term_type, debug=debug)
    color_print(ser, "=== BBS Directory ===", Color.YELLOW, term_type, debug=debug)
    safe_print(ser, "", term_type, debug=debug)

    for i, bbs in enumerate(bbs_entries, start=1):
        color_print(ser, f"{i}. {bbs.name}", Color.GREEN, term_type, debug=debug)
        if bbs.description:
            color_print(ser, f"   {bbs.description}", Color.WHITE, term_type, debug=debug)

    safe_print(ser, "", term_type, debug=debug)
    color_print(ser, "0. Hang up", Color.RED, term_type, debug=debug)
    safe_print(ser, "", term_type, debug=debug)


def get_selection(
    ser: serial.Serial,
    bbs_entries: List[BBSEntry],
    term_type: TerminalType,
    debug: bool = False,
) -> Optional[BBSEntry]:
    """
    Get user's BBS selection.

    Args:
        ser: Serial port object.
        bbs_entries: List of available BBS entries.
        term_type: Terminal type for charset-safe output.
        debug: Enable debug logging.

    Returns:
        Selected BBSEntry, or None if user chose to hang up.
    """
    max_choice = len(bbs_entries)

    while True:
        color_print(ser, f"Enter choice (1-{max_choice}, 0 to hang up): ", Color.CYAN, term_type, debug=debug)
        ch = modem_getch(ser, debug=debug)

        try:
            choice = int(ch.decode(errors="ignore"))
        except (ValueError, UnicodeDecodeError):
            color_print(ser, "Invalid input. Try again.", Color.RED, term_type, debug=debug)
            continue

        if choice == 0:
            logger.info("User chose to hang up")
            return None

        if 1 <= choice <= max_choice:
            selected = bbs_entries[choice - 1]
            logger.info(f"User selected BBS: {selected.name}")
            color_print(ser, f"Connecting to {selected.name}...", Color.GREEN, term_type, debug=debug)
            return selected

        color_print(ser, f"Please enter 1-{max_choice} or 0.", Color.YELLOW, term_type, debug=debug)
