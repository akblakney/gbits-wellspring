"""
MetricsService — global, ever-increasing counters for bytes served and
bytes archived (broken down by archive reason).

Loads any existing counts from MetricsRepository at construction time
(so a restart doesn't reset to zero), keeps them in memory for fast
increments, and persists after every update -- see module docstring in
metrics_repository.py for why persist-on-every-write is fine at this
traffic volume.

No per-hour/per-day breakdown here on purpose (per your requirements --
this is a simple global running total, not a time series). If you want
historical trends over time later, that's a different feature (e.g.
snapshotting these totals periodically) layered on top of this, not a
change to this class.
"""

import logging
import threading
from typing import Any

from repository.metrics_repository import MetricsRepository

logger = logging.getLogger(__name__)

_DEFAULT_COUNTERS: dict[str, Any] = {
    "bytes_served": 0,
    "bytes_archived": 0,
    "pairs_kept": 0,
    "pairs_discarded": 0
}


class MetricsService:
    def __init__(self, metrics_repository: MetricsRepository):
        self._metrics_repository = metrics_repository
        self._lock = threading.Lock()

        loaded = self._metrics_repository.read()
        self._counters: dict[str, Any] = loaded if loaded is not None else dict(_DEFAULT_COUNTERS)
        # Guard against a partially-shaped file (e.g. from an older version)
        for key in _DEFAULT_COUNTERS:
            self._counters.setdefault(key, 0)

        logger.info("Metrics loaded: %s", self._counters)

    def record_metric(self, metric_name: str, inc: int) -> None:
        if inc <= 0:
            return
        with self._lock:
            self._counters[metric_name] += inc
            self._persist_locked()

    def get_summary(self) -> dict[str, Any]:
        """Thread-safe snapshot of current totals."""
        with self._lock:
            # Return a copy so callers can't mutate internal state.
            return { key: self._counters[key] for key in _DEFAULT_COUNTERS}

    def _persist_locked(self) -> None:
        """Must be called while holding self._lock."""
        try:
            self._metrics_repository.write(self._counters)
        except OSError:
            # Same philosophy as ArchiveService: a disk hiccup here
            # shouldn't take down serving/archiving. Log loudly; the
            # in-memory counters are still correct, just not yet
            # durable -- next successful write will catch them up.
            logger.error("Failed to persist metrics -- in-memory counts still correct", exc_info=True)