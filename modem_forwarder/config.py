"""Configuration loading and dataclasses for Modem Forwarder."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class AutoLoginStep:
    """Single step in an auto-login sequence."""
    action: str  # 'wait', 'send', 'send_raw', 'delay'
    value: Any   # string for wait/send/send_raw, int for delay (ms)


@dataclass
class BBSEntry:
    """Configuration for a single BBS."""
    name: str
    host: str
    port: int
    description: str = ""
    protocol: str = "telnet"  # "telnet", "ssh", "rlogin"
    auto_login: Optional[List[AutoLoginStep]] = None


@dataclass
class GlobalConfig:
    """Global configuration settings."""
    modem_port: str = "/dev/ttyUSB0"
    default_baudrate: int = 38400
    serial_timeout: float = 0
    modem_read_chunk: int = 1
    bbs_read_chunk: int = 1024
    hangup_read_timeout: float = 0.5
    debug_modem: bool = False
    welcome_message: str = "Welcome to the BBS Gateway!"
    log_file: str = "modem_forwarder.log"
    log_level: str = "INFO"
    init_sequence: List[str] = field(default_factory=lambda: [
        "ATZ", "AT&D0", "AT&C0", "ATV1", "ATS0=1"
    ])
    external_bbs_url: str = "https://syncterm.bbsdev.net/syncterm.lst"
    external_bbs_cache: str = "syncterm_cache.lst"


@dataclass
class Config:
    """Complete configuration."""
    global_config: GlobalConfig
    bbs_entries: List[BBSEntry]


def _parse_auto_login(steps_data: Optional[List[dict]]) -> Optional[List[AutoLoginStep]]:
    """Parse auto-login steps from YAML data."""
    if steps_data is None:
        return None

    steps = []
    for step_dict in steps_data:
        # Each step is a dict with one key (the action) and value
        for action, value in step_dict.items():
            steps.append(AutoLoginStep(action=action, value=value))
    return steps


def _parse_bbs_entry(data: dict) -> BBSEntry:
    """Parse a single BBS entry from YAML data."""
    return BBSEntry(
        name=data["name"],
        host=data["host"],
        port=data["port"],
        description=data.get("description", ""),
        protocol=data.get("protocol", "telnet"),
        auto_login=_parse_auto_login(data.get("auto_login")),
    )


def _parse_global_config(data: dict) -> GlobalConfig:
    """Parse global config from YAML data."""
    return GlobalConfig(
        modem_port=data.get("modem_port", "/dev/ttyUSB0"),
        default_baudrate=data.get("default_baudrate", 9600),
        serial_timeout=data.get("serial_timeout", 0),
        modem_read_chunk=data.get("modem_read_chunk", 1),
        bbs_read_chunk=data.get("bbs_read_chunk", 1024),
        hangup_read_timeout=data.get("hangup_read_timeout", 0.5),
        debug_modem=data.get("debug_modem", False),
        welcome_message=data.get("welcome_message", "Welcome to the BBS Gateway!"),
        log_file=data.get("log_file", "modem_forwarder.log"),
        log_level=data.get("log_level", "INFO"),
        init_sequence=data.get("init_sequence", ["ATZ", "AT&D0", "AT&C0", "ATV1", "ATS0=1"]),
        external_bbs_url=data.get("external_bbs_url", "https://syncterm.bbsdev.net/syncterm.lst"),
        external_bbs_cache=data.get("external_bbs_cache", "syncterm_cache.lst"),
    )


def load_config(config_path: str = "config.yaml") -> Config:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML config file.

    Returns:
        Config object with global settings and BBS entries.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If config file is invalid YAML.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    global_config = _parse_global_config(data.get("global", {}))

    bbs_entries = []
    for entry_data in data.get("bbs_entries", []):
        bbs_entries.append(_parse_bbs_entry(entry_data))

    logger.info(f"Loaded config with {len(bbs_entries)} BBS entries")

    return Config(global_config=global_config, bbs_entries=bbs_entries)
