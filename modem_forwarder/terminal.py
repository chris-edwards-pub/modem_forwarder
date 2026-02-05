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
    modem_print(ser, "4. VT100", debug=debug)
    modem_print(ser, "", debug=debug)

    while True:
        ch = modem_getch(ser, prompt="Enter choice (1-4): ", debug=debug)

        try:
            choice = int(ch.decode(errors="ignore"))
        except (ValueError, UnicodeDecodeError):
            modem_print(ser, "Invalid input. Please enter 1-4.", debug=debug)
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
        elif choice == 4:
            logger.info("User selected VT100 terminal")
            return TerminalType.VT100
        else:
            modem_print(ser, "Please enter 1, 2, 3, or 4.", debug=debug)


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


def safe_print(ser: serial.Serial, text: str, term_type: TerminalType, debug: bool = False) -> None:
    """
    Output text in a charset-safe manner for the terminal type.

    For now, uses plain text which is safe across all terminal types.
    Future enhancement: could add terminal-specific formatting.

    Args:
        ser: Serial port object.
        text: Text to output.
        term_type: Target terminal type.
        debug: Enable debug logging.
    """
    # Plain text is safe for all terminal types
    # CRLF line endings work universally
    modem_print(ser, text, debug=debug)
