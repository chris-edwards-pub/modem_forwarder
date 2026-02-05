"""Tests for config module."""

import pytest
from modem_forwarder.config import (
    load_config,
    BBSEntry,
    GlobalConfig,
    AutoLoginStep,
    _parse_auto_login,
    _parse_bbs_entry,
)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_success(self, sample_config_yaml):
        """Test loading a valid config file."""
        config = load_config(sample_config_yaml)

        assert config.global_config.modem_port == "/dev/ttyUSB0"
        assert config.global_config.default_baudrate == 9600
        assert config.global_config.welcome_message == "Test BBS Gateway"
        assert len(config.bbs_entries) == 2

    def test_load_config_bbs_entries(self, sample_config_yaml):
        """Test BBS entries are parsed correctly."""
        config = load_config(sample_config_yaml)

        bbs1 = config.bbs_entries[0]
        assert bbs1.name == "Test BBS 1"
        assert bbs1.host == "test1.example.com"
        assert bbs1.port == 23
        assert bbs1.auto_login is None

        bbs2 = config.bbs_entries[1]
        assert bbs2.name == "Test BBS 2"
        assert bbs2.auto_login is not None
        assert len(bbs2.auto_login) == 4

    def test_load_config_file_not_found(self):
        """Test loading a non-existent config file."""
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")

    def test_load_config_defaults(self, tmp_path):
        """Test that defaults are used for missing values."""
        config_content = """
global: {}
bbs_entries: []
"""
        config_file = tmp_path / "minimal.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert config.global_config.modem_port == "/dev/ttyUSB0"
        assert config.global_config.default_baudrate == 9600
        assert config.global_config.log_level == "INFO"


class TestParseAutoLogin:
    """Tests for auto-login parsing."""

    def test_parse_auto_login_none(self):
        """Test parsing null auto_login."""
        result = _parse_auto_login(None)
        assert result is None

    def test_parse_auto_login_steps(self):
        """Test parsing auto-login steps."""
        steps_data = [
            {"wait": "login:"},
            {"send": "user"},
            {"delay": 500},
        ]
        result = _parse_auto_login(steps_data)

        assert len(result) == 3
        assert result[0].action == "wait"
        assert result[0].value == "login:"
        assert result[1].action == "send"
        assert result[1].value == "user"
        assert result[2].action == "delay"
        assert result[2].value == 500


class TestParseBBSEntry:
    """Tests for BBS entry parsing."""

    def test_parse_bbs_entry_minimal(self):
        """Test parsing minimal BBS entry."""
        data = {
            "name": "Test",
            "host": "example.com",
            "port": 23,
        }
        result = _parse_bbs_entry(data)

        assert result.name == "Test"
        assert result.host == "example.com"
        assert result.port == 23
        assert result.description == ""
        assert result.auto_login is None

    def test_parse_bbs_entry_full(self):
        """Test parsing full BBS entry."""
        data = {
            "name": "Full Test",
            "host": "example.com",
            "port": 6400,
            "description": "A full test entry",
            "auto_login": [
                {"wait": "ready"},
            ],
        }
        result = _parse_bbs_entry(data)

        assert result.name == "Full Test"
        assert result.description == "A full test entry"
        assert result.auto_login is not None
        assert len(result.auto_login) == 1
