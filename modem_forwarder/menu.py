"""Menu display and selection system."""

import logging
from typing import List, Optional, Union

import serial

from .config import BBSEntry
from .modem import modem_getch, modem_input
from .terminal import TerminalType, safe_print, color_print, Color

logger = logging.getLogger(__name__)

# Special return value indicating user wants external BBS menu
EXTERNAL_MENU = "external"


def display_menu(
    ser: serial.Serial,
    bbs_entries: List[BBSEntry],
    welcome_message: str,
    term_type: TerminalType,
    external_count: int = 0,
    debug: bool = False,
) -> None:
    """
    Display the BBS selection menu to the modem user.

    Args:
        ser: Serial port object.
        bbs_entries: List of available BBS entries.
        welcome_message: Welcome message to display.
        term_type: Terminal type for charset-safe output.
        external_count: Number of external BBSes available.
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

    if external_count > 0:
        color_print(ser, f"X. External BBSes ({external_count}+)", Color.CYAN, term_type, debug=debug)

    color_print(ser, "0. Hang up", Color.RED, term_type, debug=debug)
    safe_print(ser, "", term_type, debug=debug)


def get_selection(
    ser: serial.Serial,
    bbs_entries: List[BBSEntry],
    term_type: TerminalType,
    has_external: bool = False,
    debug: bool = False,
) -> Union[BBSEntry, str, None]:
    """
    Get user's BBS selection.

    Args:
        ser: Serial port object.
        bbs_entries: List of available BBS entries.
        term_type: Terminal type for charset-safe output.
        has_external: Whether external BBS menu is available.
        debug: Enable debug logging.

    Returns:
        Selected BBSEntry, EXTERNAL_MENU constant, or None if user chose to hang up.
    """
    max_choice = len(bbs_entries)
    prompt_extra = ", X for external" if has_external else ""

    while True:
        color_print(ser, f"Enter choice (1-{max_choice}{prompt_extra}, 0 to hang up): ", Color.CYAN, term_type, debug=debug)
        ch = modem_getch(ser, debug=debug)
        ch_str = ch.decode(errors="ignore").upper()

        # Check for external menu
        if has_external and ch_str == "X":
            logger.info("User selected external BBS menu")
            return EXTERNAL_MENU

        try:
            choice = int(ch_str)
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


def display_external_menu(
    ser: serial.Serial,
    external_bbs: List[BBSEntry],
    term_type: TerminalType,
    page_size: int = 15,
    debug: bool = False,
) -> Optional[BBSEntry]:
    """
    Display paginated external BBS list with search.

    Args:
        ser: Serial port object.
        external_bbs: List of external BBS entries.
        term_type: Terminal type for charset-safe output.
        page_size: Number of entries per page.
        debug: Enable debug logging.

    Returns:
        Selected BBSEntry, or None to return to main menu.
    """
    if not external_bbs:
        color_print(ser, "No external BBSes available.", Color.RED, term_type, debug=debug)
        return None

    # Working list (can be filtered by search)
    display_list = external_bbs
    search_query = ""
    page = 0

    while True:
        # Calculate pagination
        total_pages = (len(display_list) + page_size - 1) // page_size
        if total_pages == 0:
            total_pages = 1
        page = max(0, min(page, total_pages - 1))

        start_idx = page * page_size
        end_idx = min(start_idx + page_size, len(display_list))
        page_entries = display_list[start_idx:end_idx]

        # Display header
        safe_print(ser, "", term_type, debug=debug)
        if search_query:
            header = f'=== Search: "{search_query}" ({len(display_list)} results) ==='
        else:
            header = f"=== External BBSes (Page {page + 1}/{total_pages}) ==="
        color_print(ser, header, Color.YELLOW, term_type, debug=debug)
        safe_print(ser, "", term_type, debug=debug)

        # Display entries
        for i, bbs in enumerate(page_entries, start=1):
            protocol_tag = f"[{bbs.protocol}]"
            color_print(ser, f"{i:2}. {bbs.name[:30]:<30} {protocol_tag}", Color.GREEN, term_type, debug=debug)

        safe_print(ser, "", term_type, debug=debug)

        # Display navigation options
        nav_options = []
        if page < total_pages - 1:
            nav_options.append("[N]ext")
        if page > 0:
            nav_options.append("[P]rev")
        nav_options.append("[S]earch")
        if search_query:
            nav_options.append("[C]lear")
        nav_options.append("[0] Back")

        color_print(ser, "  ".join(nav_options), Color.CYAN, term_type, debug=debug)
        safe_print(ser, "", term_type, debug=debug)

        # Get selection
        result = get_external_selection(
            ser, page_entries, term_type,
            has_next=(page < total_pages - 1),
            has_prev=(page > 0),
            has_clear=bool(search_query),
            debug=debug
        )

        if result == "next":
            page += 1
        elif result == "prev":
            page -= 1
        elif result == "search":
            search_query = prompt_search_term(ser, term_type, debug)
            if search_query:
                from .syncterm import search_bbs_list
                display_list = search_bbs_list(external_bbs, search_query)
                page = 0
                if not display_list:
                    color_print(ser, "No matches found.", Color.RED, term_type, debug=debug)
                    display_list = external_bbs
                    search_query = ""
            else:
                display_list = external_bbs
        elif result == "clear":
            display_list = external_bbs
            search_query = ""
            page = 0
        elif result == "back":
            return None
        elif isinstance(result, BBSEntry):
            return result


def get_external_selection(
    ser: serial.Serial,
    page_entries: List[BBSEntry],
    term_type: TerminalType,
    has_next: bool = False,
    has_prev: bool = False,
    has_clear: bool = False,
    debug: bool = False,
) -> Union[BBSEntry, str]:
    """
    Get user selection from external BBS page.

    Args:
        ser: Serial port object.
        page_entries: BBS entries on current page.
        term_type: Terminal type.
        has_next: Whether next page exists.
        has_prev: Whether previous page exists.
        has_clear: Whether search can be cleared.
        debug: Enable debug logging.

    Returns:
        BBSEntry, or command string ("next", "prev", "search", "clear", "back").
    """
    max_choice = len(page_entries)

    while True:
        color_print(ser, "Selection: ", Color.CYAN, term_type, debug=debug)
        ch = modem_getch(ser, debug=debug)
        ch_str = ch.decode(errors="ignore").upper()

        # Navigation commands
        if ch_str == "N" and has_next:
            return "next"
        if ch_str == "P" and has_prev:
            return "prev"
        if ch_str == "S":
            return "search"
        if ch_str == "C" and has_clear:
            return "clear"
        if ch_str == "0":
            return "back"

        # Numeric selection
        try:
            choice = int(ch_str)
            if 1 <= choice <= max_choice:
                selected = page_entries[choice - 1]
                logger.info(f"User selected external BBS: {selected.name}")
                color_print(ser, f"Connecting to {selected.name}...", Color.GREEN, term_type, debug=debug)
                return selected
        except ValueError:
            pass

        color_print(ser, "Invalid choice.", Color.RED, term_type, debug=debug)


def prompt_search_term(
    ser: serial.Serial,
    term_type: TerminalType,
    debug: bool = False,
) -> str:
    """
    Prompt user for search term.

    Args:
        ser: Serial port object.
        term_type: Terminal type.
        debug: Enable debug logging.

    Returns:
        Search string entered by user.
    """
    safe_print(ser, "", term_type, debug=debug)
    search = modem_input(ser, prompt="Search: ", debug=debug)
    return search.strip()
