"""Call logging with SQLite storage."""

import logging
import sqlite3
import time
from datetime import datetime, date

logger = logging.getLogger(__name__)

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    duration_secs INTEGER,
    baud_rate TEXT,
    terminal_type TEXT,
    bbs_name TEXT,
    protocol TEXT,
    disconnect_reason TEXT
)
"""


class CallLog:
    """SQLite-backed call/session logging."""

    def __init__(self, db_path="call_log.db"):
        logger.info(f"Opening call log database: {db_path}")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(CREATE_TABLE)
        self.conn.commit()

    def start_session(self, baud_rate=None, terminal_type=None):
        """Record a new session. Returns the session ID."""
        now = datetime.now()
        cursor = self.conn.execute(
            "INSERT INTO sessions (started_at, baud_rate, terminal_type) VALUES (?, ?, ?)",
            (now, baud_rate, terminal_type),
        )
        self.conn.commit()
        session_id = cursor.lastrowid
        logger.info(f"Call log: session {session_id} started (baud={baud_rate}, term={terminal_type})")
        return session_id

    def log_bbs_selection(self, session_id, bbs_name, protocol="telnet"):
        """Record which BBS was selected for a session."""
        self.conn.execute(
            "UPDATE sessions SET bbs_name = ?, protocol = ? WHERE id = ?",
            (bbs_name, protocol, session_id),
        )
        self.conn.commit()
        logger.info(f"Call log: session {session_id} selected {bbs_name} ({protocol})")

    def end_session(self, session_id, disconnect_reason="unknown"):
        """Finalize a session with end time and disconnect reason."""
        now = datetime.now()
        row = self.conn.execute(
            "SELECT started_at FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        duration = 0
        if row and row["started_at"]:
            started = datetime.fromisoformat(row["started_at"])
            duration = int((now - started).total_seconds())
        self.conn.execute(
            "UPDATE sessions SET ended_at = ?, duration_secs = ?, disconnect_reason = ? WHERE id = ?",
            (now, duration, disconnect_reason, session_id),
        )
        self.conn.commit()
        logger.info(f"Call log: session {session_id} ended ({disconnect_reason}, {duration}s)")

    def get_stats(self):
        """Return usage statistics dict."""
        stats = {}

        # Total calls
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM sessions").fetchone()
        stats["total_calls"] = row["cnt"]

        # Calls today
        today = date.today().isoformat()
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM sessions WHERE DATE(started_at) = ?", (today,)
        ).fetchone()
        stats["calls_today"] = row["cnt"]

        # Average duration
        row = self.conn.execute(
            "SELECT AVG(duration_secs) as avg_dur FROM sessions WHERE duration_secs IS NOT NULL"
        ).fetchone()
        stats["avg_duration_secs"] = int(row["avg_dur"] or 0)

        # Top 5 BBSes
        rows = self.conn.execute(
            "SELECT bbs_name, COUNT(*) as cnt FROM sessions WHERE bbs_name IS NOT NULL "
            "GROUP BY bbs_name ORDER BY cnt DESC LIMIT 5"
        ).fetchall()
        stats["top_bbs"] = [(r["bbs_name"], r["cnt"]) for r in rows]

        # Most common baud rate
        row = self.conn.execute(
            "SELECT baud_rate, COUNT(*) as cnt FROM sessions WHERE baud_rate IS NOT NULL "
            "GROUP BY baud_rate ORDER BY cnt DESC LIMIT 1"
        ).fetchone()
        stats["top_baud_rate"] = row["baud_rate"] if row else None

        # Most common terminal type
        row = self.conn.execute(
            "SELECT terminal_type, COUNT(*) as cnt FROM sessions WHERE terminal_type IS NOT NULL "
            "GROUP BY terminal_type ORDER BY cnt DESC LIMIT 1"
        ).fetchone()
        stats["top_terminal"] = row["terminal_type"] if row else None

        return stats

    def close(self):
        """Close the database connection."""
        self.conn.close()
