"""Tests for auto-login module."""

import pytest
from unittest.mock import MagicMock, patch
import time

from modem_forwarder.autologin import execute_autologin
from modem_forwarder.config import AutoLoginStep


class TestExecuteAutologin:
    """Tests for auto-login execution."""

    def test_execute_autologin_send(self, mock_socket):
        """Test sending text during auto-login."""
        steps = [
            AutoLoginStep(action="send", value="hello"),
        ]

        result = execute_autologin(mock_socket, steps)

        assert result is True
        mock_socket.sendall.assert_called_once_with(b"hello\r")

    def test_execute_autologin_send_raw(self, mock_socket):
        """Test sending raw text (no CR) during auto-login."""
        steps = [
            AutoLoginStep(action="send_raw", value="raw"),
        ]

        result = execute_autologin(mock_socket, steps)

        assert result is True
        mock_socket.sendall.assert_called_once_with(b"raw")

    def test_execute_autologin_delay(self, mock_socket):
        """Test delay action during auto-login."""
        steps = [
            AutoLoginStep(action="delay", value=50),  # 50ms
        ]

        start = time.time()
        result = execute_autologin(mock_socket, steps)
        elapsed = time.time() - start

        assert result is True
        assert elapsed >= 0.05  # At least 50ms

    def test_execute_autologin_wait_success(self, mock_socket):
        """Test wait action with matching response."""
        steps = [
            AutoLoginStep(action="wait", value="login:"),
        ]

        # Simulate receiving the expected text
        mock_socket.recv.return_value = b"Welcome!\nlogin: "

        result = execute_autologin(mock_socket, steps, timeout=1.0)

        assert result is True

    def test_execute_autologin_wait_timeout(self, mock_socket):
        """Test wait action timeout."""
        steps = [
            AutoLoginStep(action="wait", value="never_appears"),
        ]

        # Simulate receiving unrelated text
        mock_socket.recv.return_value = b"something else"

        result = execute_autologin(mock_socket, steps, timeout=0.1)

        assert result is False

    def test_execute_autologin_wait_connection_closed(self, mock_socket):
        """Test wait action when connection closes."""
        steps = [
            AutoLoginStep(action="wait", value="login:"),
        ]

        # Simulate connection close
        mock_socket.recv.return_value = b""

        result = execute_autologin(mock_socket, steps, timeout=1.0)

        assert result is False

    def test_execute_autologin_multiple_steps(self, mock_socket):
        """Test executing multiple auto-login steps."""
        steps = [
            AutoLoginStep(action="wait", value="login:"),
            AutoLoginStep(action="send", value="user"),
            AutoLoginStep(action="wait", value="password:"),
            AutoLoginStep(action="send", value="pass"),
        ]

        # Simulate receiving prompts
        responses = [b"login: ", b"password: "]
        mock_socket.recv.side_effect = responses

        result = execute_autologin(mock_socket, steps, timeout=1.0)

        assert result is True
        assert mock_socket.sendall.call_count == 2

    def test_execute_autologin_empty_steps(self, mock_socket):
        """Test executing with no steps."""
        steps = []

        result = execute_autologin(mock_socket, steps)

        assert result is True

    def test_execute_autologin_unknown_action(self, mock_socket):
        """Test handling unknown action type."""
        steps = [
            AutoLoginStep(action="unknown", value="test"),
        ]

        # Should complete (with warning) but not fail
        result = execute_autologin(mock_socket, steps)

        assert result is True
