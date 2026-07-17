"""
ArchiveService — the "archived" exit path.

Owns the policy of *when* something gets archived (expired off the pool
front, or excess bytes left over from a serve/beacon call); delegates
the actual persistence mechanics to ArchiveRepository.
"""

import logging

from repository.pool_repository import PoolRepository
from repository.archive_repository import ArchiveRepository
from model.chunk import Chunk
from config import config
from service.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class ArchiveService:
    def __init__(self, pool_repository: PoolRepository, metrics_service: MetricsService, archive_repository: ArchiveRepository | None = None ):
        self._pool_repository = pool_repository
        self.metrics_service = metrics_service
        self._archive_repository = archive_repository or ArchiveRepository()

    def sweep_expired(self) -> None:
        """
        Pop chunks off the front of the pool while they're older than TTL.
        Since the pool is FIFO-ordered by creation time, we can stop as
        soon as we hit a chunk that isn't expired yet.
        """
        while True:
            front = self._pool_repository.peek_front()
            if front is None:
                return
            if front.age_seconds() < config.POOL_TTL_SECONDS:
                return

            expired = self._pool_repository.pop_front()
            if expired is not None:
                self._archive(expired, reason="expired")

    def archive_excess(self, chunk: Chunk) -> None:
        """
        Called by serve/beacon services when a popped chunk had more
        bytes than were actually needed.
        """
        self._archive(chunk, reason="excess")

    def _archive(self, chunk: Chunk, reason: str) -> None:
        try:
            self._archive_repository.write_chunk(chunk, reason)
            self.metrics_service.record_metric('bytes_archived', len(chunk))
            if chunk.pairs_discarded is not None:
                self.metrics_service.record_metric('pairs_discarded', chunk.pairs_discarded)
            if chunk.pairs_kept is not None:
                self.metrics_service.record_metric('pairs_kept', chunk.pairs_kept)
            logger.debug(
                "Archived chunk (reason=%s, bytes=%d, age=%.2fs)",
                reason, len(chunk), chunk.age_seconds(),
            )
        except OSError:
            # Archiving is best-effort against disk/IO failures: we do NOT
            # want a disk hiccup to take down generation or serving. Log
            # loudly so it's visible, but let the caller proceed. The bytes
            # are lost in this case -- worth monitoring/alerting on later.
            logger.error(
                "Failed to archive chunk (reason=%s, bytes=%d) -- bytes lost",
                reason, len(chunk), exc_info=True,
            )