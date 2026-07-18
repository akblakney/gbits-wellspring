"""
BeaconService — creates and serves randomness beacon pulses.
"""

import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Iterable

from repository.pool_repository import PoolRepository
from repository.beacon_repository import BeaconRepository
from service.archive_service import ArchiveService
from model.chunk import Chunk
from config import config

logger = logging.getLogger(__name__)

GENESIS_PREVIOUS_HASH = "0" * 64


class PulseGenerationError(Exception):
    """Raised when a pulse could not be generated (timeout or pool race)."""
    pass


class BeaconService:
    def __init__(
        self,
        pool_repository: PoolRepository,
        archive_service: ArchiveService,
        beacon_repository: BeaconRepository,
    ):
        self._pool_repository = pool_repository
        self._archive_service = archive_service
        self._beacon_repository = beacon_repository

        self._create_lock = threading.Lock()

    def create_pulse(self, intended_timestamp: datetime | None = None) -> dict[str, Any]:
        with self._create_lock:
            raw_bytes = self._draw_with_wait(config.BEACON_OUTPUT_BYTES)

            latest = self._beacon_repository.get_latest()
            pulse_index = 0 if latest is None else latest["pulse_index"] + 1
            previous_hash = GENESIS_PREVIOUS_HASH if latest is None else latest["pulse_hash"]

            if intended_timestamp is not None:
                timestamp_utc = intended_timestamp
            else:
                timestamp_utc = self._align_to_pulse_boundary(datetime.now(timezone.utc))

            pulse = {
                "pulse_index": pulse_index,
                "timestamp_utc": timestamp_utc.isoformat(),
                "output_value": raw_bytes.hex(),
                "previous_hash": previous_hash,
            }
            pulse["pulse_hash"] = self._compute_pulse_hash(pulse)

            self._beacon_repository.append(pulse)
            logger.info("Created beacon pulse index=%d", pulse_index)
            return pulse

    def get_latest(self) -> dict[str, Any] | None:
        return self._beacon_repository.get_latest()

    def get_by_index(self, pulse_index: int) -> dict[str, Any] | None:
        return self._beacon_repository.get_by_index(pulse_index)

    def get_by_timestamp(self, timestamp_utc: datetime) -> dict[str, Any] | None:
        aligned = self._align_to_pulse_boundary(timestamp_utc)
        return self._beacon_repository.get_by_timestamp(aligned)

    @staticmethod
    def verify_chain(pulses: "Iterable[dict[str, Any]]") -> bool:
        expected_previous_hash = None
        for i, pulse in enumerate(pulses):
            if i == 0:
                expected_previous_hash = pulse["previous_hash"]
            elif pulse["previous_hash"] != expected_previous_hash:
                logger.warning("Chain break at pulse_index=%s: previous_hash mismatch", pulse["pulse_index"])
                return False

            if BeaconService._compute_pulse_hash(pulse) != pulse["pulse_hash"]:
                logger.warning("Chain break at pulse_index=%s: pulse_hash mismatch", pulse["pulse_index"])
                return False

            expected_previous_hash = pulse["pulse_hash"]
        return True

    @staticmethod
    def _align_to_pulse_boundary(timestamp_utc: datetime) -> datetime:
        """Round down to the nearest pulse interval boundary (e.g. top of minute)."""
        epoch_seconds = timestamp_utc.timestamp()
        aligned_seconds = epoch_seconds - (epoch_seconds % config.BEACON_PULSE_INTERVAL_SECONDS)
        return datetime.fromtimestamp(aligned_seconds, tz=timezone.utc)

    @staticmethod
    def _compute_pulse_hash(pulse: dict[str, Any]) -> str:
        # Hash over every field except pulse_hash itself, fixed key
        # order, so anyone can independently recompute and verify it.
        payload = json.dumps(
            {
                "pulse_index": pulse["pulse_index"],
                "timestamp_utc": pulse["timestamp_utc"],
                "output_value": pulse["output_value"],
                "previous_hash": pulse["previous_hash"],
            },
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _draw_with_wait(self, num_bytes: int) -> bytes:
        deadline = time.monotonic() + config.BEACON_WAIT_TIMEOUT_SECONDS
        while True:
            available = self._pool_repository.total_bytes()
            if available >= num_bytes:
                return self._draw_bytes(num_bytes)

            if time.monotonic() >= deadline:
                raise PulseGenerationError(
                    f"Pool could not supply {num_bytes} bytes for beacon pulse within "
                    f"{config.BEACON_WAIT_TIMEOUT_SECONDS}s (only {available} available)"
                )

            time.sleep(config.BEACON_WAIT_POLL_INTERVAL_SECONDS)

    def _draw_bytes(self, num_bytes: int) -> bytes:
        collected = bytearray()
        while len(collected) < num_bytes:
            chunk = self._pool_repository.pop_front()
            if chunk is None:
                raise PulseGenerationError(
                    f"Pool exhausted mid-draw for beacon pulse: needed {num_bytes} bytes, "
                    f"only collected {len(collected)}"
                )

            remaining_needed = num_bytes - len(collected)
            if len(chunk) <= remaining_needed:
                collected.extend(chunk.data)
            else:
                used = chunk.data[:remaining_needed]
                excess = chunk.data[remaining_needed:]
                collected.extend(used)
                excess_chunk = Chunk(data=excess, created_at=chunk.created_at, audio_samples=None, pairs_discarded=chunk.pairs_discarded, pairs_kept=chunk.pairs_kept)
                self._archive_service.archive_excess(excess_chunk)

        return bytes(collected[:num_bytes])