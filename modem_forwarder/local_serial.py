"""Local serial port emulation using stdin/stdout for testing without a modem."""

import os
import select
import sys
import termios
import tty


class LocalSerial:
    """Drop-in replacement for serial.Serial that uses the local terminal."""

    is_local = True

    def __init__(self):
        self._stdin_fd = sys.stdin.fileno()
        self._stdout_fd = sys.stdout.fileno()
        self._old_settings = termios.tcgetattr(self._stdin_fd)
        tty.setraw(self._stdin_fd)
        self._closed = False

    # --- Properties expected by modem.py ---

    @property
    def in_waiting(self) -> int:
        """Return number of bytes available to read (0 or 1)."""
        r, _, _ = select.select([self._stdin_fd], [], [], 0)
        return 1 if r else 0

    @property
    def dtr(self) -> bool:
        return True

    @dtr.setter
    def dtr(self, value: bool) -> None:
        pass

    @property
    def xonxoff(self) -> bool:
        return False

    @xonxoff.setter
    def xonxoff(self, value: bool) -> None:
        pass

    # --- Core I/O ---

    def write(self, data: bytes) -> int:
        """Write bytes to stdout."""
        return os.write(self._stdout_fd, data)

    def read(self, size: int = 1) -> bytes:
        """Read bytes from stdin."""
        return os.read(self._stdin_fd, size)

    def flush(self) -> None:
        """Flush stdout."""
        try:
            os.fsync(self._stdout_fd)
        except OSError:
            pass

    def fileno(self) -> int:
        """Return stdin file descriptor for use with selectors."""
        return self._stdin_fd

    # --- No-ops for modem-specific operations ---

    def reset_input_buffer(self) -> None:
        pass

    def flushInput(self) -> None:
        pass

    # --- Context manager ---

    def close(self) -> None:
        """Restore terminal settings."""
        if not self._closed:
            termios.tcsetattr(self._stdin_fd, termios.TCSADRAIN, self._old_settings)
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
