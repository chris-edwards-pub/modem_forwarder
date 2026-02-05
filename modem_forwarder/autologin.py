"""Auto-login macro execution."""

import logging
import time
from typing import List

from .config import AutoLoginStep

logger = logging.getLogger(__name__)

DEFAULT_WAIT_TIMEOUT = 30.0  # seconds


def execute_autologin(
    sock,
    steps: List[AutoLoginStep],
    timeout: float = DEFAULT_WAIT_TIMEOUT,
) -> bool:
    """
    Execute auto-login sequence on socket.

    Args:
        sock: Connected socket (should be in blocking mode).
        steps: List of AutoLoginStep actions.
        timeout: Timeout for wait actions (seconds).

    Returns:
        True if all steps completed, False on timeout/error.
    """
    logger.info(f"Executing auto-login sequence with {len(steps)} steps")
    buffer = ""

    for i, step in enumerate(steps):
        logger.debug(f"Auto-login step {i + 1}: {step.action} = {step.value!r}")

        if step.action == "wait":
            # Accumulate data until we see the target string
            deadline = time.time() + timeout
            target = step.value.lower()

            while target not in buffer.lower():
                if time.time() > deadline:
                    logger.warning(f"Timeout waiting for: {step.value!r}")
                    return False
                try:
                    data = sock.recv(1024)
                    if not data:
                        logger.warning("Connection closed during auto-login")
                        return False
                    decoded = data.decode(errors='ignore')
                    buffer += decoded
                    logger.debug(f"Received: {decoded!r}")
                except BlockingIOError:
                    time.sleep(0.05)
                except Exception as e:
                    logger.error(f"Error during auto-login wait: {e}")
                    return False

            logger.debug(f"Found target string: {step.value!r}")
            buffer = ""  # Clear buffer after match

        elif step.action == "send":
            text = step.value + "\r"
            logger.debug(f"Sending: {text!r}")
            try:
                sock.sendall(text.encode())
            except Exception as e:
                logger.error(f"Error during auto-login send: {e}")
                return False

        elif step.action == "send_raw":
            logger.debug(f"Sending raw: {step.value!r}")
            try:
                sock.sendall(step.value.encode())
            except Exception as e:
                logger.error(f"Error during auto-login send_raw: {e}")
                return False

        elif step.action == "delay":
            delay_ms = step.value
            delay_sec = delay_ms / 1000.0
            logger.debug(f"Delaying {delay_ms}ms")
            time.sleep(delay_sec)

        else:
            logger.warning(f"Unknown auto-login action: {step.action}")

    logger.info("Auto-login sequence completed successfully")
    return True
