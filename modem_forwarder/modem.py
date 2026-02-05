"""Modem serial I/O functions."""

import logging
import time
from typing import List, Optional

import serial

logger = logging.getLogger(__name__)


def modem_print(ser: serial.Serial, text: str, debug: bool = False) -> None:
    """
    Send a string to the modem, appending CRLF, and flush.

    Args:
        ser: Serial port object.
        text: Text to send.
        debug: Enable debug logging.
    """
    if not text.endswith("\r\n"):
        text = text + "\r\n"
    btext = text.encode(errors="replace")
    if debug:
        logger.debug(f"Writing to modem: {btext!r}")
    ser.write(btext)
    ser.flush()


def modem_input(ser: serial.Serial, prompt: Optional[str] = None, debug: bool = False) -> str:
    """
    Optionally send a prompt, then read and return a line of input from the modem.

    Args:
        ser: Serial port object.
        prompt: Optional prompt to display before reading.
        debug: Enable debug logging.

    Returns:
        The input line (without line ending).
    """
    if prompt:
        modem_print(ser, prompt, debug=debug)
    buf = b""
    while True:
        waiting = ser.in_waiting
        if waiting:
            if debug:
                logger.debug(f"Reading {waiting} bytes from modem during modem_input")
            ch = ser.read(1)
            if debug:
                logger.debug(f"Read byte: {ch!r}")
            if ch in (b'\r', b'\n'):
                if buf:
                    break
                else:
                    continue  # ignore leading newlines
            buf += ch
        else:
            time.sleep(0.05)
    return buf.decode(errors="replace")


def modem_getch(ser: serial.Serial, prompt: Optional[str] = None, debug: bool = False) -> bytes:
    """
    Optionally send a prompt, then wait for and return a single character from the modem.

    Args:
        ser: Serial port object.
        prompt: Optional prompt to display before reading.
        debug: Enable debug logging.

    Returns:
        Single byte read from modem.
    """
    if prompt:
        modem_print(ser, prompt, debug=debug)
    while True:
        waiting = ser.in_waiting
        if waiting:
            if debug:
                logger.debug(f"Reading {waiting} bytes from modem during modem_getch")
            ch = ser.read(1)
            if debug:
                logger.debug(f"Read byte: {ch!r}")
            return ch
        time.sleep(0.05)


def force_hangup(ser: serial.Serial, debug: bool = False) -> None:
    """
    Force the modem to drop any existing connection: DTR toggle, escape, ATH.
    Waits briefly for 'OK' or 'NO CARRIER'.

    Args:
        ser: Serial port object.
        debug: Enable debug logging.
    """
    logger.info("Forcing hangup: DTR drop + escape + ATH")
    try:
        # Hard drop via DTR toggle
        ser.dtr = False
        if debug:
            logger.debug("DTR set to False")
        time.sleep(1)
        ser.dtr = True
        if debug:
            logger.debug("DTR set to True")
        time.sleep(0.5)

        # Guard time before escape
        time.sleep(0.5)
        if debug:
            logger.debug("Writing to modem: b'+++'")
        ser.write(b"+++")
        ser.flush()
        time.sleep(1)

        # Hang up
        if debug:
            logger.debug("Writing to modem: b'ATH\\r'")
        ser.write(b"ATH\r")
        ser.flush()

        # Wait for acknowledgement, up to 5 seconds
        deadline = time.time() + 5.0
        resp = ""
        while time.time() < deadline:
            waiting = ser.in_waiting
            if waiting:
                if debug:
                    logger.debug(f"Reading {waiting} bytes from modem during hangup wait")
                chunk = ser.read(waiting)
                if debug:
                    logger.debug(f"Read bytes: {chunk!r}")
                chunk_decoded = chunk.decode(errors="ignore")
                resp += chunk_decoded
                if "OK" in resp.upper() or "NO CARRIER" in resp.upper():
                    logger.info(f"Hangup response: {resp.strip()!r}")
                    return
            time.sleep(0.05)
        logger.warning(f"Hangup timeout, last response: {resp.strip()!r}")
    except Exception as e:
        logger.error(f"force_hangup exception: {e}")


def init_modem(ser: serial.Serial, init_sequence: Optional[List[str]] = None, debug: bool = False) -> None:
    """
    Initialize the modem with AT commands.

    Args:
        ser: Serial port object.
        init_sequence: List of AT commands (without \\r). Defaults to standard sequence.
        debug: Enable debug logging.
    """
    if init_sequence is None:
        init_sequence = ["ATZ", "AT&D0", "AT&C0", "ATV1", "ATS0=1"]

    logger.info("Initializing modem...")
    for cmd in init_sequence:
        cmd_bytes = (cmd + "\r").encode()
        if debug:
            logger.debug(f"Sending init command: {cmd_bytes!r}")
        ser.write(cmd_bytes)
        ser.flush()
        time.sleep(1)


def wait_for_connect(ser: serial.Serial, debug: bool = False) -> str:
    """
    Wait for an incoming call and CONNECT response from the modem.

    Args:
        ser: Serial port object.
        debug: Enable debug logging.

    Returns:
        The CONNECT string from the modem (e.g., "CONNECT 9600/ARQ/V42").
    """
    logger.info("Waiting for incoming call...")
    buffer = ""
    raw_buffer = ""  # Preserve original case for display
    while True:
        waiting = ser.in_waiting
        if waiting:
            if debug:
                logger.debug(f"Reading {waiting} bytes from modem during connect wait")
            data = ser.read(waiting)
            if debug:
                logger.debug(f"Read bytes: {data!r}")
            data_decoded = data.decode(errors="ignore")
            logger.info(f"Modem says: {data_decoded.strip()}")
            raw_buffer += data_decoded
            buffer += data_decoded.upper()
            if "CONNECT" in buffer:
                # Extract the CONNECT line from raw buffer
                connect_string = ""
                for line in raw_buffer.split('\n'):
                    if "CONNECT" in line.upper():
                        connect_string = line.strip()
                        break
                logger.info(f"CONNECT detected: {connect_string}")
                # Flush input buffer
                if hasattr(ser, 'reset_input_buffer'):
                    if debug:
                        logger.debug("Flushing modem input buffer (reset_input_buffer)")
                    ser.reset_input_buffer()
                else:
                    if debug:
                        logger.debug("Flushing modem input buffer (flushInput)")
                    ser.flushInput()
                time.sleep(0.1)  # Let any noise settle
                # Drain any remaining characters
                while ser.in_waiting:
                    remaining = ser.in_waiting
                    if debug:
                        logger.debug(f"Draining {remaining} bytes from modem input buffer")
                    ser.read(remaining)
                return connect_string
        time.sleep(0.05)


def flush_input_buffer(ser: serial.Serial, debug: bool = False) -> None:
    """
    Flush the serial input buffer.

    Args:
        ser: Serial port object.
        debug: Enable debug logging.
    """
    if hasattr(ser, 'reset_input_buffer'):
        if debug:
            logger.debug("Flushing modem input buffer (reset_input_buffer)")
        ser.reset_input_buffer()
    else:
        if debug:
            logger.debug("Flushing modem input buffer (flushInput)")
        ser.flushInput()

    # Drain any remaining characters
    while ser.in_waiting:
        remaining = ser.in_waiting
        if debug:
            logger.debug(f"Draining {remaining} bytes from modem input buffer")
        ser.read(remaining)
