"""Prometheus metrics for Grafana Cloud integration."""

import logging
import threading
import time

logger = logging.getLogger(__name__)

try:
    from prometheus_client import CollectorRegistry, Counter, Histogram, push_to_gateway
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False


class Metrics:
    """Prometheus metrics with periodic push to Grafana Cloud."""

    def __init__(self, url="", user="", api_key="", push_interval=60):
        self.enabled = bool(url and user and api_key and HAS_PROMETHEUS)

        if not self.enabled:
            if url and not HAS_PROMETHEUS:
                logger.warning("prometheus_client not installed, metrics disabled")
            elif not url:
                logger.info("Grafana Cloud not configured, metrics disabled")
            return

        self.url = url
        self.user = user
        self.api_key = api_key
        self.registry = CollectorRegistry()

        self.calls_total = Counter(
            "modem_calls_total", "Total calls",
            labelnames=["disconnect_reason"],
            registry=self.registry,
        )
        self.session_duration = Histogram(
            "modem_session_duration_seconds", "Session duration",
            buckets=[30, 60, 120, 300, 600, 1800, 3600, 7200],
            registry=self.registry,
        )
        self.bbs_selections = Counter(
            "modem_bbs_selections_total", "BBS selections",
            labelnames=["bbs_name", "protocol"],
            registry=self.registry,
        )
        self.connects = Counter(
            "modem_connects_total", "Connections by baud/terminal",
            labelnames=["baud_rate", "terminal_type"],
            registry=self.registry,
        )

        self._stop_event = threading.Event()
        self._push_thread = threading.Thread(
            target=self._push_loop, args=(push_interval,), daemon=True
        )
        self._push_thread.start()
        logger.info(f"Grafana Cloud metrics enabled (push every {push_interval}s)")

    def record_connect(self, baud_rate, terminal_type):
        """Record a new connection."""
        if not self.enabled:
            return
        self.connects.labels(baud_rate=baud_rate or "unknown", terminal_type=terminal_type or "unknown").inc()

    def record_bbs_selection(self, bbs_name, protocol):
        """Record a BBS selection."""
        if not self.enabled:
            return
        self.bbs_selections.labels(bbs_name=bbs_name, protocol=protocol).inc()

    def record_session_end(self, duration_secs, disconnect_reason):
        """Record session end with duration and reason."""
        if not self.enabled:
            return
        self.calls_total.labels(disconnect_reason=disconnect_reason).inc()
        self.session_duration.observe(duration_secs)

    def _push_loop(self, interval):
        """Periodically push metrics to Grafana Cloud."""
        while not self._stop_event.wait(interval):
            self._push()

    def _push(self):
        """Push metrics to Grafana Cloud Prometheus endpoint."""
        try:
            from prometheus_client.exposition import basic_auth_handler

            def auth_handler(url, method, timeout, headers, data):
                return basic_auth_handler(url, method, timeout, headers, data,
                                          self.user, self.api_key)

            push_to_gateway(
                self.url, job="modem_forwarder",
                registry=self.registry, handler=auth_handler,
            )
            logger.debug("Metrics pushed to Grafana Cloud")
        except Exception as e:
            logger.warning(f"Failed to push metrics: {e}")

    def stop(self):
        """Stop the push thread and do a final push."""
        if not self.enabled:
            return
        self._stop_event.set()
        self._push()
