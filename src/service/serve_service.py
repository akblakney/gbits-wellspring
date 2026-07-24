"""
Pops whole chunks off the front of the pool until enough bytes have been
accumulated to satisfy a request, returns exactly what was asked for, and
routes any leftover bytes from the final (overshooting) chunk to the
archive service as "excess" rather than discarding them silently.
"""

import math

from repository.pool_repository import PoolRepository
from service.archive_service import ArchiveService
from service.metrics_service import MetricsService
from model.chunk import Chunk
from model.response.bits_response import BitsResponse
from config import config


class InsufficientPoolDataError(Exception):
    """Raised when the pool cannot currently satisfy a serve request."""
    pass


class ServeService:
    def __init__(self, pool_repository: PoolRepository, archive_service: ArchiveService, metrics_service: MetricsService):
        self._pool_repository = pool_repository
        self._archive_service = archive_service
        self.metrics_service = metrics_service

    def serve_bits(self, num_bytes: int) -> BitsResponse:

        if num_bytes <= 0:
            raise ValueError("num_bytes must be positive")
        if num_bytes > config.MAX_BYTES_PER_REQUEST:
            raise ValueError(f"num_bytes exceeds max allowed ({config.MAX_BYTES_PER_REQUEST})")

        available = self._pool_repository.total_bytes()
        if available < num_bytes:
            raise InsufficientPoolDataError(
                f"Pool cannot satisfy request: needed {num_bytes} bytes, "
                f"only {available} available"
            )

        collected = bytearray()
        samples = []
        pairs_discarded = 0
        pairs_kept = 0
        total_chunks = 0

        while len(collected) < num_bytes:
            chunk = self._pool_repository.pop_front()
            if chunk is None:
                # Should not happen given the availability check above,
                # unless another consumer raced us for the same bytes.
                raise InsufficientPoolDataError(
                    f"Pool exhausted mid-read (likely concurrent consumer): "
                    f"needed {num_bytes} bytes, only collected {len(collected)}"
                )

            remaining_needed = num_bytes - len(collected)

            samples.extend(chunk.audio_samples)
            pairs_discarded += chunk.pairs_discarded
            pairs_kept += chunk.pairs_kept
            total_chunks += 1

            if len(chunk) <= remaining_needed:
                collected.extend(chunk.data)
            else:
                used = chunk.data[:remaining_needed]
                excess = chunk.data[remaining_needed:]
                collected.extend(used)

                excess_chunk = Chunk(data=excess, created_at=chunk.created_at, audio_samples=chunk.audio_samples)
                self._archive_service.archive_excess(excess_chunk)

        self.metrics_service.record_metric('bytes_served', num_bytes)
        result_bytes = bytes(collected[:num_bytes])
        return BitsResponse(result_bytes, samples, pairs_discarded=pairs_discarded, pairs_kept=pairs_kept, total_chunks=total_chunks)
