"""Terminal type detection and charset-safe output."""

import logging
import time
from enum import Enum
from typing import Optional

import serial

from .modem import modem_print, modem_getch

logger = logging.getLogger(__name__)


class TerminalType(Enum):
    """Supported terminal types."""
    PETSCII = "petscii"
    ANSI = "ansi"
    ASCII = "ascii"
    VT100 = "vt100"


class Color(Enum):
    """Semantic color names for terminal output."""
    RESET = "reset"
    WHITE = "white"
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    YELLOW = "yellow"
    CYAN = "cyan"
    PURPLE = "purple"


# ANSI/VT100 color escape codes
ANSI_COLORS = {
    Color.RESET: "\x1b[0m",
    Color.WHITE: "\x1b[37m",
    Color.RED: "\x1b[31m",
    Color.GREEN: "\x1b[32m",
    Color.BLUE: "\x1b[34m",
    Color.YELLOW: "\x1b[33m",
    Color.CYAN: "\x1b[36m",
    Color.PURPLE: "\x1b[35m",
}

# PETSCII color control characters (accent/lowercase glyph region in $00-$1F, some $80-$9F)
PETSCII_COLORS = {
    Color.RESET: "\x05",      # CHR$(5) = white (reset to default)
    Color.WHITE: "\x05",      # CHR$(5) = white
    Color.RED: "\x1c",        # CHR$(28) = red
    Color.GREEN: "\x1e",      # CHR$(30) = green
    Color.BLUE: "\x1f",       # CHR$(31) = blue
    Color.YELLOW: "\x9e",     # CHR$(158) = yellow
    Color.CYAN: "\x9f",       # CHR$(159) = cyan
    Color.PURPLE: "\x9c",     # CHR$(156) = purple
}


# ANSI escape sequence to request cursor position
ANSI_CURSOR_POSITION_REQUEST = b"\x1b[6n"

# Expected response pattern: ESC [ row ; col R
# We just check for ESC [ ... R pattern


def detect_terminal(ser: serial.Serial, timeout: float = 2.0, debug: bool = False) -> Optional[TerminalType]:
    """
    Attempt to auto-detect terminal type.

    Sends ANSI cursor position request and checks for response.
    ANSI/VT100 terminals will respond with cursor position.
    PETSCII terminals will not respond (or respond differently).

    Args:
        ser: Serial port object.
        timeout: How long to wait for response (seconds).
        debug: Enable debug logging.

    Returns:
        Detected TerminalType, or None if detection failed.
    """
    logger.info("Attempting terminal type detection...")

    # Clear any pending input
    while ser.in_waiting:
        ser.read(ser.in_waiting)

    # Send ANSI cursor position request
    if debug:
        logger.debug(f"Sending ANSI cursor position request: {ANSI_CURSOR_POSITION_REQUEST!r}")
    ser.write(ANSI_CURSOR_POSITION_REQUEST)
    ser.flush()

    # Wait for response
    deadline = time.time() + timeout
    response = b""

    while time.time() < deadline:
        if ser.in_waiting:
            chunk = ser.read(ser.in_waiting)
            response += chunk
            if debug:
                logger.debug(f"Received during detection: {chunk!r}")

            # Check for ANSI response pattern: ESC [ digits ; digits R
            if b"\x1b[" in response and b"R" in response:
                logger.info("Detected ANSI/VT100 terminal (responded to cursor position request)")
                # Determine if it's ANSI or VT100 - for now treat as ANSI
                return TerminalType.ANSI

        time.sleep(0.05)

    # No ANSI response - could be PETSCII or plain ASCII
    if response:
        # Got some response but not ANSI - might be PETSCII echoing back
        logger.info(f"Got non-ANSI response during detection: {response!r}")

    logger.info("Terminal detection inconclusive, will prompt user")
    return None


def prompt_terminal_type(ser: serial.Serial, debug: bool = False) -> TerminalType:
    """
    Ask user to select terminal type.

    Args:
        ser: Serial port object.
        debug: Enable debug logging.

    Returns:
        Selected TerminalType.
    """
    logger.info("Prompting user for terminal type selection")

    modem_print(ser, "", debug=debug)
    modem_print(ser, "Select your terminal type:", debug=debug)
    modem_print(ser, "1. PETSCII (Commodore)", debug=debug)
    modem_print(ser, "2. ANSI", debug=debug)
    modem_print(ser, "3. ASCII (plain text)", debug=debug)
    modem_print(ser, "", debug=debug)

    while True:
        ch = modem_getch(ser, prompt="Enter choice (1-3): ", debug=debug)

        try:
            choice = int(ch.decode(errors="ignore"))
        except (ValueError, UnicodeDecodeError):
            modem_print(ser, "Invalid input. Please enter 1-3.", debug=debug)
            continue

        if choice == 1:
            logger.info("User selected PETSCII terminal")
            return TerminalType.PETSCII
        elif choice == 2:
            logger.info("User selected ANSI terminal")
            return TerminalType.ANSI
        elif choice == 3:
            logger.info("User selected ASCII terminal")
            return TerminalType.ASCII
        else:
            modem_print(ser, "Please enter 1, 2, or 3.", debug=debug)


def get_terminal_type(ser: serial.Serial, timeout: float = 2.0, debug: bool = False) -> TerminalType:
    """
    Get terminal type by auto-detection or user prompt.

    First attempts auto-detection. If that fails, prompts the user.

    Args:
        ser: Serial port object.
        timeout: Detection timeout (seconds).
        debug: Enable debug logging.

    Returns:
        TerminalType (detected or user-selected).
    """
    detected = detect_terminal(ser, timeout=timeout, debug=debug)

    if detected is not None:
        modem_print(ser, f"Detected terminal type: {detected.value.upper()}", debug=debug)
        return detected

    return prompt_terminal_type(ser, debug=debug)


def ascii_to_petscii(text: str) -> str:
    """
    Convert ASCII text to PETSCII-compatible encoding.

    PETSCII has inverted case mapping compared to ASCII:
    - ASCII uppercase (A-Z) displays as lowercase on C64
    - ASCII lowercase (a-z) displays as UPPERCASE on C64

    This function swaps case so text displays correctly on C64.

    Args:
        text: ASCII text to convert.

    Returns:
        Text with case swapped for PETSCII display.
    """
    return text.swapcase()


def get_color_code(color: Color, term_type: TerminalType) -> str:
    """
    Get the color escape/control code for a terminal type.

    Args:
        color: The color to get.
        term_type: Target terminal type.

    Returns:
        Color code string, or empty string for ASCII (no color support).
    """
    if term_type == TerminalType.PETSCII:
        return PETSCII_COLORS.get(color, "")
    elif term_type in (TerminalType.ANSI, TerminalType.VT100):
        return ANSI_COLORS.get(color, "")
    else:
        # ASCII has no color support
        return ""


def colorize(text: str, color: Color, term_type: TerminalType) -> str:
    """
    Wrap text with color codes for the terminal type.

    Args:
        text: Text to colorize.
        color: Color to apply.
        term_type: Target terminal type.

    Returns:
        Text with color codes prepended (and reset appended for ANSI).
    """
    if term_type == TerminalType.ASCII:
        return text

    color_code = get_color_code(color, term_type)
    reset_code = get_color_code(Color.RESET, term_type)

    if term_type in (TerminalType.ANSI, TerminalType.VT100):
        # ANSI needs reset at end
        return f"{color_code}{text}{reset_code}"
    else:
        # PETSCII color stays until changed
        return f"{color_code}{text}"


def safe_print(ser: serial.Serial, text: str, term_type: TerminalType, debug: bool = False) -> None:
    """
    Output text in a charset-safe manner for the terminal type.

    For PETSCII terminals, swaps case so text displays correctly on C64.
    For other terminals, sends text as-is.

    Args:
        ser: Serial port object.
        text: Text to output.
        term_type: Target terminal type.
        debug: Enable debug logging.
    """
    if term_type == TerminalType.PETSCII:
        text = ascii_to_petscii(text)

    modem_print(ser, text, debug=debug)


def color_print(
    ser: serial.Serial,
    text: str,
    color: Color,
    term_type: TerminalType,
    debug: bool = False,
) -> None:
    """
    Output colored text in a charset-safe manner for the terminal type.

    Args:
        ser: Serial port object.
        text: Text to output.
        color: Color to apply.
        term_type: Target terminal type.
        debug: Enable debug logging.
    """
    colored_text = colorize(text, color, term_type)

    if term_type == TerminalType.PETSCII:
        colored_text = get_color_code(color, term_type) + ascii_to_petscii(text)

    modem_print(ser, colored_text, debug=debug)
