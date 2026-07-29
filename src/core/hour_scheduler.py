
import logging
import threading
import time
from datetime import datetime, timezone

from service.stats_service import StatsService, NoArchivedDataError
from config import config

logger = logging.getLogger(__name__)

class HourScheduler:
    def __init__(self, stats_service: StatsService):
        self._stats_service = stats_service
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        logger.info("HourScheduler started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        logger.info("HourScheduler stopped")

    def run(self) -> None:
        while not self._stop_event.is_set():
            boundary = self._sleep_until_next_boundary()
            if self._stop_event.is_set():
                return
            try:
                self._stats_service.get_latest_completed_hour_summary()
                logger.info("scheduler - Successfully fetched stats for latest hour")
            except NoArchivedDataError:
                logger.error("skipping stats fetch for this hour, no archived data available", exc_info=True)
            except Exception:
                logger.error("Unexpected error fetching latest stats hour", exc_info=True)

    # sleeps until 10s after next hour boundary, just to be safe
    def _sleep_until_next_boundary(self) -> datetime:
        now = time.time()
        interval = 3600
        next_boundary_epoch = (now // interval + 1) * interval
        wait_seconds = next_boundary_epoch - now + 10
        self._stop_event.wait(wait_seconds)
        return datetime.fromtimestamp(next_boundary_epoch, tz=timezone.utc)