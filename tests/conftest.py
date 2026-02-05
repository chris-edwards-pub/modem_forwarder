"""Pytest fixtures for Modem Forwarder tests."""

import pytest
from unittest.mock import MagicMock, PropertyMock
from io import BytesIO


@pytest.fixture
def mock_serial():
    """Mock serial port for testing."""
    mock = MagicMock()
    mock.in_waiting = 0
    mock.read.return_value = b""
    mock.write.return_value = None
    mock.flush.return_value = None
    mock.dtr = True
    return mock


@pytest.fixture
def mock_socket():
    """Mock socket for testing."""
    mock = MagicMock()
    mock.recv.return_value = b""
    mock.sendall.return_value = None
    mock.setblocking.return_value = None
    mock.close.return_value = None
    return mock


@pytest.fixture
def sample_config_yaml(tmp_path):
    """Create a sample config.yaml file for testing."""
    config_content = """
global:
  modem_port: "/dev/ttyUSB0"
  default_baudrate: 9600
  welcome_message: "Test BBS Gateway"
  log_file: "test.log"
  log_level: "DEBUG"

bbs_entries:
  - name: "Test BBS 1"
    description: "A test BBS"
    host: "test1.example.com"
    port: 23
    auto_login: null

  - name: "Test BBS 2"
    description: "Another test BBS"
    host: "test2.example.com"
    port: 6400
    auto_login:
      - wait: "login:"
      - send: "testuser"
      - wait: "password:"
      - send: "testpass"
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def sample_bbs_entries():
    """Sample BBS entries for testing."""
    from modem_forwarder.config import BBSEntry, AutoLoginStep

    return [
        BBSEntry(
            name="Test BBS 1",
            description="A test BBS",
            host="test1.example.com",
            port=23,
            auto_login=None,
        ),
        BBSEntry(
            name="Test BBS 2",
            description="Another test BBS",
            host="test2.example.com",
            port=6400,
            auto_login=[
                AutoLoginStep(action="wait", value="login:"),
                AutoLoginStep(action="send", value="testuser"),
            ],
        ),
    ]
