"""Tests for terminal detection module."""

import pytest
from unittest.mock import MagicMock, patch, call

from modem_forwarder.terminal import (
    TerminalType,
    detect_terminal,
    prompt_terminal_type,
    get_terminal_type,
    safe_print,
    ANSI_CURSOR_POSITION_REQUEST,
)


class TestDetectTerminal:
    """Tests for terminal detection."""

    def test_detect_ansi_terminal(self, mock_serial):
        """Test detecting ANSI terminal from cursor position response."""
        # Simulate ANSI response to cursor position request
        mock_serial.in_waiting = 0
        responses = [b"\x1b[24;80R"]  # ESC [ row ; col R
        call_count = [0]

        def mock_in_waiting():
            if call_count[0] < 5:
                call_count[0] += 1
                return 0
            return len(responses[0]) if responses else 0

        def mock_read(n):
            if responses:
                return responses.pop(0)
            return b""

        mock_serial.in_waiting = property(lambda self: mock_in_waiting())
        type(mock_serial).in_waiting = property(lambda self: mock_in_waiting())
        mock_serial.read.side_effect = mock_read

        result = detect_terminal(mock_serial, timeout=0.2)

        # Should have sent cursor position request
        mock_serial.write.assert_called_with(ANSI_CURSOR_POSITION_REQUEST)

    def test_detect_no_response(self, mock_serial):
        """Test detection with no response."""
        mock_serial.in_waiting = 0
        type(mock_serial).in_waiting = property(lambda self: 0)

        result = detect_terminal(mock_serial, timeout=0.1)

        assert result is None


class TestPromptTerminalType:
    """Tests for terminal type prompting."""

    def test_prompt_petscii(self, mock_serial):
        """Test selecting PETSCII terminal."""
        mock_serial.in_waiting = 1
        type(mock_serial).in_waiting = property(lambda self: 1)
        mock_serial.read.return_value = b"1"

        result = prompt_terminal_type(mock_serial)

        assert result == TerminalType.PETSCII

    def test_prompt_ansi(self, mock_serial):
        """Test selecting ANSI terminal."""
        mock_serial.in_waiting = 1
        type(mock_serial).in_waiting = property(lambda self: 1)
        mock_serial.read.return_value = b"2"

        result = prompt_terminal_type(mock_serial)

        assert result == TerminalType.ANSI

    def test_prompt_ascii(self, mock_serial):
        """Test selecting ASCII terminal."""
        mock_serial.in_waiting = 1
        type(mock_serial).in_waiting = property(lambda self: 1)
        mock_serial.read.return_value = b"3"

        result = prompt_terminal_type(mock_serial)

        assert result == TerminalType.ASCII

    def test_prompt_vt100(self, mock_serial):
        """Test selecting VT100 terminal."""
        mock_serial.in_waiting = 1
        type(mock_serial).in_waiting = property(lambda self: 1)
        mock_serial.read.return_value = b"4"

        result = prompt_terminal_type(mock_serial)

        assert result == TerminalType.VT100


class TestGetTerminalType:
    """Tests for get_terminal_type function."""

    @patch('modem_forwarder.terminal.detect_terminal')
    @patch('modem_forwarder.terminal.prompt_terminal_type')
    def test_get_terminal_type_detected(self, mock_prompt, mock_detect, mock_serial):
        """Test when terminal type is auto-detected."""
        mock_detect.return_value = TerminalType.ANSI

        result = get_terminal_type(mock_serial)

        assert result == TerminalType.ANSI
        mock_prompt.assert_not_called()

    @patch('modem_forwarder.terminal.detect_terminal')
    @patch('modem_forwarder.terminal.prompt_terminal_type')
    def test_get_terminal_type_prompt_fallback(self, mock_prompt, mock_detect, mock_serial):
        """Test fallback to prompting when detection fails."""
        mock_detect.return_value = None
        mock_prompt.return_value = TerminalType.PETSCII

        result = get_terminal_type(mock_serial)

        assert result == TerminalType.PETSCII
        mock_prompt.assert_called_once()


class TestSafePrint:
    """Tests for safe_print function."""

    def test_safe_print_adds_crlf(self, mock_serial):
        """Test that safe_print sends text with CRLF."""
        safe_print(mock_serial, "Hello", TerminalType.ASCII)

        mock_serial.write.assert_called()
        call_args = mock_serial.write.call_args[0][0]
        assert call_args.endswith(b"\r\n")
