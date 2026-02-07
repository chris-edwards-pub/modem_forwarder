"""Bridge session handling for telnet, SSH, and rlogin."""

import logging
import selectors
import time

import serial

from .autologin import execute_autologin
from .config import BBSEntry, GlobalConfig
from .modem import force_hangup, modem_print
from .protocols import create_connection

logger = logging.getLogger(__name__)


def bridge_session(
    ser: serial.Serial,
    bbs: BBSEntry,
    config: GlobalConfig,
) -> None:
    """
    Bridge modem to BBS via telnet, SSH, or rlogin.

    Args:
        ser: Serial port object.
        bbs: BBS configuration (host, port, protocol, auto_login, etc.).
        config: Global settings (chunk sizes, debug flag).
    """
    protocol = getattr(bbs, 'protocol', 'telnet')
    logger.info(f"Connecting to {bbs.name} at {bbs.host}:{bbs.port} via {protocol}...")

    sock = create_connection(bbs, ser, debug=config.debug_modem, timeout=10)
    if sock is None:
        logger.error(f"Could not connect to {bbs.name}")
        modem_print(ser, "Connection failed.", debug=config.debug_modem)
        return False

    logger.info(f"Connected to {bbs.name} via {protocol}")

    # Execute auto-login if configured
    if bbs.auto_login:
        logger.info("Running auto-login sequence...")
        sock.setblocking(True)
        success = execute_autologin(sock, bbs.auto_login)
        if not success:
            logger.warning("Auto-login did not complete successfully")
            modem_print(ser, "Auto-login failed, continuing anyway...", debug=config.debug_modem)
    else:
        logger.debug("No auto-login configured, skipping")

    sock.setblocking(False)
    sel = selectors.DefaultSelector()
    sel.register(ser, selectors.EVENT_READ, data="modem")
    sel.register(sock, selectors.EVENT_READ, data="bbs")

    idle_timeout = config.idle_timeout
    logger.info(f"Connection established. Entering bridge loop... (idle timeout: {idle_timeout}s)")

    last_activity = time.time()
    try:
        while True:
            events = sel.select(1)
            if not events:
                if idle_timeout and time.time() - last_activity > idle_timeout:
                    logger.warning(f"Session timed out after {idle_timeout}s of inactivity")
                    modem_print(ser, "\r\nSession timed out due to inactivity.", debug=config.debug_modem)
                    return
                continue

            # Check for carrier loss (caller hung up)
            if not getattr(ser, 'is_local', False) and not ser.cd:
                logger.info("Carrier lost (caller disconnected). Ending session.")
                return

            for key, mask in events:
                source = key.data

                if source == "modem":
                    try:
                        data = ser.read(ser.in_waiting or config.modem_read_chunk)
                    except Exception as e:
                        logger.error(f"Error reading modem: {e}")
                        data = b""

                    if data:
                        last_activity = time.time()
                        if config.debug_modem:
                            logger.debug(f"Modem->Telnet: {len(data)} bytes: {data[:80]!r}")
                        try:
                            sock.sendall(data)
                        except Exception as e:
                            logger.error(f"Send to BBS failed: {e}")
                            return

                elif source == "bbs":
                    try:
                        data = sock.recv(config.bbs_read_chunk)
                    except BlockingIOError:
                        data = b""
                    except Exception as e:
                        logger.error(f"Error reading BBS: {e}")
                        data = b""

                    if data:
                        last_activity = time.time()
                        if config.debug_modem:
                            logger.debug(f"Telnet->Modem: {len(data)} bytes: {data[:80]!r}")
                        try:
                            ser.write(data)
                            ser.flush()
                        except Exception as e:
                            logger.error(f"Write to modem failed: {e}")
                            return
                    elif data == b"":
                        # Remote side closed
                        logger.info("BBS closed connection. Ending session.")
                        return

    finally:
        try:
            sel.unregister(ser)
            sel.unregister(sock)
        except Exception:
            pass
        sock.close()
        logger.info("Bridge loop exited, forcing hangup.")
        force_hangup(ser, debug=config.debug_modem)
