"""
StatsService — policy layer for statistical test results.

Only ever operates on the latest COMPLETED hour (never the current,
still-being-written one), so the underlying .bin file is guaranteed
immutable and the .stats.json cache never goes stale.

Depends on a `test_runner` callable injected at construction time:
    test_runner(data: np.ndarray) -> dict
This keeps the actual statistical tests decoupled from this service —
plug in your real test suite in main.py.
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import numpy as np

from repository.stats_repository import StatsRepository
from stats.summary import compute_stats

logger = logging.getLogger(__name__)


class NoArchivedDataError(Exception):
    """Raised when the latest completed hour has no archived .bin data at all."""
    pass


class StatsService:
    def __init__(
        self,
        stats_repository: StatsRepository,
    ):
        self._stats_repository = stats_repository
        self._compute_lock = threading.Lock()

    def get_latest_completed_hour_summary(self) -> dict[str, Any]:
        return self.get_summary_for_hour(self._latest_completed_hour_start())

    def get_summary_for_hour(self, hour_start: datetime) -> dict[str, Any]:
        
        cached = self._stats_repository.read(hour_start)
        if cached is not None:
            logger.info("Stats cache hit for hour %s", hour_start.isoformat())
            return cached

        with self._compute_lock:
            cached = self._stats_repository.read(hour_start)
            if cached is not None:
                logger.info("Stats cache hit (post-lock) for hour %s", hour_start.isoformat())
                return cached

            logger.info("Stats cache miss for hour %s, computing now", hour_start.isoformat())
            results = self._compute_for_hour(hour_start)
            self._stats_repository.write(hour_start, results)
            return results

    def _compute_for_hour(self, hour_start: datetime) -> dict[str, Any]:
        bin_path = self._stats_repository.bin_path_for_hour(hour_start)
        if not bin_path.exists():
            raise NoArchivedDataError(
                f"No archived data for hour {hour_start.isoformat()} (expected {bin_path})"
            )

        raw_bytes = bin_path.read_bytes()
        if len(raw_bytes) == 0:
            raise NoArchivedDataError(f"Archive file for hour {hour_start.isoformat()} is empty")

        data = np.frombuffer(raw_bytes, dtype=np.uint8)
        test_results = compute_stats(data, 'hourly stats')

        return {
            "hour_start_utc": hour_start.isoformat(),
            "num_bytes_tested": len(raw_bytes),
            "tests": test_results,
        }

    @staticmethod
    def _latest_completed_hour_start() -> datetime:
        now = datetime.now(timezone.utc)
        current_hour_start = now.replace(minute=0, second=0, microsecond=0)
        return current_hour_start - timedelta(hours=1)