"""Protocol-specific connection handlers for telnet, SSH, and rlogin."""

import logging
import socket
from typing import Union

import serial

from .config import BBSEntry
from .modem import modem_print, modem_input, modem_getch

logger = logging.getLogger(__name__)


class SSHChannelWrapper:
    """Wrap paramiko channel to provide socket-like interface for selectors."""

    def __init__(self, channel):
        self.channel = channel
        self._fileno = channel.fileno()

    def fileno(self):
        return self._fileno

    def recv(self, bufsize: int) -> bytes:
        return self.channel.recv(bufsize)

    def sendall(self, data: bytes) -> None:
        self.channel.sendall(data)

    def close(self) -> None:
        self.channel.close()

    def setblocking(self, flag: bool) -> None:
        self.channel.setblocking(flag)


def create_connection(
    bbs: BBSEntry,
    ser: serial.Serial,
    debug: bool = False,
    timeout: int = 10,
) -> Union[socket.socket, SSHChannelWrapper, None]:
    """
    Create protocol-specific connection to BBS.

    Args:
        bbs: BBS entry with host, port, protocol.
        ser: Serial port for prompting user (SSH credentials).
        debug: Enable debug logging.
        timeout: Connection timeout in seconds.

    Returns:
        Socket-like object for the connection, or None on failure.
    """
    protocol = bbs.protocol.lower()

    if protocol == "telnet":
        return create_telnet_connection(bbs, timeout, debug)
    elif protocol == "ssh":
        return create_ssh_connection(bbs, ser, timeout, debug)
    elif protocol == "rlogin":
        return create_rlogin_connection(bbs, ser, timeout, debug)
    else:
        logger.error(f"Unknown protocol: {protocol}")
        return None


def create_telnet_connection(
    bbs: BBSEntry,
    timeout: int = 10,
    debug: bool = False,
) -> Union[socket.socket, None]:
    """
    Create raw telnet/socket connection.

    Args:
        bbs: BBS entry with host, port.
        timeout: Connection timeout.
        debug: Enable debug logging.

    Returns:
        Socket or None on failure.
    """
    try:
        if debug:
            logger.debug(f"Creating telnet connection to {bbs.host}:{bbs.port}")
        sock = socket.create_connection((bbs.host, bbs.port), timeout=timeout)
        return sock
    except Exception as e:
        logger.error(f"Telnet connection failed: {e}")
        return None


def create_ssh_connection(
    bbs: BBSEntry,
    ser: serial.Serial,
    timeout: int = 10,
    debug: bool = False,
) -> Union[SSHChannelWrapper, None]:
    """
    Create SSH connection with user credential prompts.

    Args:
        bbs: BBS entry with host, port.
        ser: Serial port for prompting user.
        timeout: Connection timeout.
        debug: Enable debug logging.

    Returns:
        SSHChannelWrapper or None on failure.
    """
    try:
        import paramiko
    except ImportError:
        logger.error("SSH support requires paramiko: pip install paramiko")
        modem_print(ser, "SSH not available (paramiko not installed)", debug=debug)
        return None

    modem_print(ser, "", debug=debug)
    modem_print(ser, f"SSH connection to {bbs.host}:{bbs.port}", debug=debug)

    while True:
        modem_print(ser, "", debug=debug)

        username = modem_input(ser, prompt="Username: ", allow_empty=True, debug=debug)

        if username:
            password = modem_input(ser, prompt="Password: ", mask_char="*", debug=debug)
        else:
            password = None

        try:
            if debug:
                logger.debug(f"Creating SSH connection to {bbs.host}:{bbs.port} as {username}")

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": bbs.host,
                "port": bbs.port,
                "timeout": timeout,
                "look_for_keys": False,
                "allow_agent": False,
            }
            if username:
                connect_kwargs["username"] = username
            if password:
                connect_kwargs["password"] = password

            client.connect(**connect_kwargs)

            # Get interactive shell channel
            channel = client.invoke_shell(term="ansi", width=80, height=24)
            channel.settimeout(0.0)  # Non-blocking

            logger.info(f"SSH connected to {bbs.host}:{bbs.port}")
            return SSHChannelWrapper(channel)

        except paramiko.AuthenticationException:
            logger.error("SSH authentication failed")
            modem_print(ser, "Authentication failed.", debug=debug)
        except paramiko.SSHException as e:
            logger.error(f"SSH error: {e}")
            modem_print(ser, f"SSH error: {e}", debug=debug)
        except Exception as e:
            logger.error(f"SSH connection failed: {e}")
            modem_print(ser, f"Connection failed: {e}", debug=debug)

        # Prompt to retry or return to menu
        modem_print(ser, "", debug=debug)
        choice = modem_getch(ser, prompt="(R)etry or (M)enu? ", debug=debug)
        if choice.upper() != b"R":
            return None


def create_rlogin_connection(
    bbs: BBSEntry,
    ser: serial.Serial,
    timeout: int = 10,
    debug: bool = False,
) -> Union[socket.socket, None]:
    """
    Create rlogin connection with RFC 1282 handshake.

    Args:
        bbs: BBS entry with host, port.
        ser: Serial port for prompting user.
        timeout: Connection timeout.
        debug: Enable debug logging.

    Returns:
        Socket or None on failure.
    """
    # Prompt for credentials
    modem_print(ser, "", debug=debug)
    modem_print(ser, f"rlogin connection to {bbs.host}:{bbs.port}", debug=debug)
    modem_print(ser, "", debug=debug)

    username = modem_input(ser, prompt="Username: ", debug=debug)
    if not username:
        modem_print(ser, "Username required.", debug=debug)
        return None

    try:
        if debug:
            logger.debug(f"Creating rlogin connection to {bbs.host}:{bbs.port} as {username}")

        sock = socket.create_connection((bbs.host, bbs.port), timeout=timeout)

        # RFC 1282 rlogin handshake:
        # \0 + local_username + \0 + remote_username + \0 + terminal/speed + \0
        handshake = b"\x00"  # Initial null
        handshake += username.encode() + b"\x00"  # Local user
        handshake += username.encode() + b"\x00"  # Remote user (same)
        handshake += b"ansi/9600\x00"  # Terminal type/speed

        sock.sendall(handshake)

        # Wait for server acknowledgement (single null byte)
        sock.settimeout(timeout)
        response = sock.recv(1)
        if response != b"\x00":
            logger.warning(f"Unexpected rlogin response: {response!r}")

        sock.settimeout(None)
        logger.info(f"rlogin connected to {bbs.host}:{bbs.port}")
        return sock

    except Exception as e:
        logger.error(f"rlogin connection failed: {e}")
        modem_print(ser, f"Connection failed: {e}", debug=debug)
        return None
