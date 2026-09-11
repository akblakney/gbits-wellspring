import logging
import threading
import time
from datetime import datetime, timezone

from service.beacon_service import BeaconService, PulseGenerationError
from service.pool_service import PoolService
from service.metrics_service import MetricsService
from config import config

logger = logging.getLogger(__name__)


class BeaconScheduler:
    def __init__(self, beacon_service: BeaconService, pool_service: PoolService, metrics_service: MetricsService):
        self._beacon_service = beacon_service
        self._pool_service = pool_service
        self._metrics_service = metrics_service
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        logger.info("BeaconScheduler started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        logger.info("BeaconScheduler stopped")

    def run(self) -> None:
        while not self._stop_event.is_set():
            boundary = self._sleep_until_next_boundary()
            if self._stop_event.is_set():
                return
            try:
                self._beacon_service.create_pulse(intended_timestamp=boundary)
            except PulseGenerationError:
                logger.error("Skipping beacon pulse this tick -- could not generate in time", exc_info=True)
            except Exception:
                logger.error("Unexpected error creating beacon pulse -- skipping this tick", exc_info=True)

            # logging

            logger.info('Pool status: %s chunks with %s bytes', self._pool_service.num_chunks(), self._pool_service.num_bytes())
            logger.info('Metrics: %s', self._metrics_service.get_summary())

    def _sleep_until_next_boundary(self) -> datetime:
        now = time.time()
        interval = config.BEACON_PULSE_INTERVAL_SECONDS
        next_boundary_epoch = (now // interval + 1) * interval
        wait_seconds = next_boundary_epoch - now
        self._stop_event.wait(wait_seconds)
        return datetime.fromtimestamp(next_boundary_epoch, tz=timezone.utc)