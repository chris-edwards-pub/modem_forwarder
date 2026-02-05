"""Tests for menu module."""

import pytest
from unittest.mock import MagicMock, patch, call

from modem_forwarder.menu import display_menu, get_selection
from modem_forwarder.terminal import TerminalType


class TestDisplayMenu:
    """Tests for menu display."""

    def test_display_menu_shows_entries(self, mock_serial, sample_bbs_entries):
        """Test that display_menu shows all BBS entries."""
        display_menu(
            mock_serial,
            sample_bbs_entries,
            "Welcome!",
            TerminalType.ASCII,
        )

        # Should have written multiple times (welcome, header, entries, etc.)
        assert mock_serial.write.call_count > 0

    def test_display_menu_shows_hangup_option(self, mock_serial, sample_bbs_entries):
        """Test that display_menu shows hang up option."""
        display_menu(
            mock_serial,
            sample_bbs_entries,
            "Welcome!",
            TerminalType.ASCII,
        )

        # Check that "Hang up" was written
        calls = mock_serial.write.call_args_list
        all_output = b"".join(c[0][0] for c in calls)
        assert b"Hang up" in all_output


class TestGetSelection:
    """Tests for menu selection."""

    def test_get_selection_valid_choice(self, mock_serial, sample_bbs_entries):
        """Test selecting a valid BBS."""
        mock_serial.in_waiting = 1
        type(mock_serial).in_waiting = property(lambda self: 1)
        mock_serial.read.return_value = b"1"

        result = get_selection(
            mock_serial,
            sample_bbs_entries,
            TerminalType.ASCII,
        )

        assert result == sample_bbs_entries[0]

    def test_get_selection_second_entry(self, mock_serial, sample_bbs_entries):
        """Test selecting the second BBS."""
        mock_serial.in_waiting = 1
        type(mock_serial).in_waiting = property(lambda self: 1)
        mock_serial.read.return_value = b"2"

        result = get_selection(
            mock_serial,
            sample_bbs_entries,
            TerminalType.ASCII,
        )

        assert result == sample_bbs_entries[1]

    def test_get_selection_hangup(self, mock_serial, sample_bbs_entries):
        """Test selecting hang up (0)."""
        mock_serial.in_waiting = 1
        type(mock_serial).in_waiting = property(lambda self: 1)
        mock_serial.read.return_value = b"0"

        result = get_selection(
            mock_serial,
            sample_bbs_entries,
            TerminalType.ASCII,
        )

        assert result is None

    def test_get_selection_invalid_then_valid(self, mock_serial, sample_bbs_entries):
        """Test invalid input followed by valid selection."""
        mock_serial.in_waiting = 1
        type(mock_serial).in_waiting = property(lambda self: 1)
        # First return invalid, then valid
        mock_serial.read.side_effect = [b"x", b"1"]

        result = get_selection(
            mock_serial,
            sample_bbs_entries,
            TerminalType.ASCII,
        )

        assert result == sample_bbs_entries[0]
