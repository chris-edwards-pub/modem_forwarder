"""Download and parse syncterm.lst BBS directory."""

import logging
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Optional

from .config import BBSEntry

logger = logging.getLogger(__name__)

# Protocol mapping from syncterm.lst to our internal names
PROTOCOL_MAP = {
    "telnet": "telnet",
    "ssh": "ssh",
    "rlogin": "rlogin",
    "raw": "telnet",  # Raw connections use telnet socket
}

# Default ports by protocol
DEFAULT_PORTS = {
    "telnet": 23,
    "ssh": 22,
    "rlogin": 513,
}


def download_syncterm_list(url: str, cache_path: str) -> List[BBSEntry]:
    """
    Download syncterm.lst from URL, fallback to cache on failure.

    Args:
        url: URL to download from.
        cache_path: Path to local cache file.

    Returns:
        List of BBSEntry objects.
    """
    content = None

    # Try downloading fresh list
    try:
        logger.info(f"Downloading external BBS list from {url}...")
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read().decode("utf-8", errors="replace")
        logger.info(f"Downloaded {len(content)} bytes")

        # Save to cache
        try:
            Path(cache_path).write_text(content, encoding="utf-8")
            logger.info(f"Cached BBS list to {cache_path}")
        except Exception as e:
            logger.warning(f"Could not cache BBS list: {e}")

    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        logger.warning(f"Could not download BBS list: {e}")

    # If download failed, try cache
    if content is None:
        cache_file = Path(cache_path)
        if cache_file.exists():
            logger.info(f"Using cached BBS list from {cache_path}")
            content = cache_file.read_text(encoding="utf-8")
        else:
            logger.error("No external BBS list available (download failed, no cache)")
            return []

    return parse_syncterm_lst(content)


def parse_syncterm_lst(content: str) -> List[BBSEntry]:
    """
    Parse syncterm.lst INI-style format into BBSEntry list.

    Format:
        [BBS Name]
            ConnectionType=telnet|ssh|rlogin
            Address=hostname
            Port=23
            Comment=Description text

    Args:
        content: Raw content of syncterm.lst file.

    Returns:
        List of BBSEntry objects.
    """
    entries = []
    current_name: Optional[str] = None
    current_data: dict = {}

    for line in content.split("\n"):
        line = line.rstrip()

        # Skip comments and empty lines
        if not line or line.startswith(";"):
            continue

        # Check for section header [BBS Name]
        section_match = re.match(r"^\[(.+)\]$", line)
        if section_match:
            # Save previous entry if exists
            if current_name and current_data.get("address"):
                entry = _create_entry(current_name, current_data)
                if entry:
                    entries.append(entry)

            # Start new entry
            current_name = section_match.group(1).strip()
            current_data = {}
            continue

        # Parse key=value pairs (may be indented)
        stripped = line.lstrip("\t ")
        if "=" in stripped:
            key, value = stripped.split("=", 1)
            key = key.lower().strip()
            value = value.strip()

            if key == "connectiontype":
                current_data["protocol"] = value.lower()
            elif key == "address":
                current_data["address"] = value
            elif key == "port":
                try:
                    current_data["port"] = int(value)
                except ValueError:
                    pass
            elif key == "comment":
                current_data["comment"] = value
        else:
            # Continuation of previous value (multiline comment)
            if current_data.get("comment"):
                current_data["comment"] += " " + stripped

    # Don't forget the last entry
    if current_name and current_data.get("address"):
        entry = _create_entry(current_name, current_data)
        if entry:
            entries.append(entry)

    logger.info(f"Parsed {len(entries)} BBS entries from syncterm.lst")
    return entries


def _create_entry(name: str, data: dict) -> Optional[BBSEntry]:
    """
    Create BBSEntry from parsed data.

    Args:
        name: BBS name from section header.
        data: Dict with address, port, protocol, comment.

    Returns:
        BBSEntry or None if invalid.
    """
    address = data.get("address")
    if not address:
        return None

    # Map protocol
    raw_protocol = data.get("protocol", "telnet")
    protocol = PROTOCOL_MAP.get(raw_protocol, "telnet")

    # Get port with default
    port = data.get("port")
    if port is None:
        port = DEFAULT_PORTS.get(protocol, 23)

    comment = data.get("comment", "")

    return BBSEntry(
        name=name,
        host=address,
        port=port,
        description=comment,
        protocol=protocol,
    )


def search_bbs_list(bbs_list: List[BBSEntry], query: str) -> List[BBSEntry]:
    """
    Filter BBS list by search query.

    Searches name and description (case-insensitive).

    Args:
        bbs_list: List of BBSEntry to search.
        query: Search string.

    Returns:
        Filtered list of matching entries.
    """
    if not query:
        return bbs_list

    query_lower = query.lower()
    results = []

    for bbs in bbs_list:
        if (query_lower in bbs.name.lower() or
                query_lower in bbs.description.lower()):
            results.append(bbs)

    return results
