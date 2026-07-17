"""
GenerationService — the entry path into the pool.

Called by the Generator once per generation cycle with freshly produced
bytes. Wraps them in a Chunk, appends to the pool, and triggers an
expiry sweep (lazy expiry, tied to producer activity as discussed).
"""

from repository.pool_repository import PoolRepository
from service.archive_service import ArchiveService
from model.chunk import Chunk
import logging
from typing import List

log = logging.getLogger(__name__)

class GenerationService:
    def __init__(self, pool_repository: PoolRepository, archive_service: ArchiveService):
        self._pool_repository = pool_repository
        self._archive_service = archive_service

    def ingest(self, chunk) -> None:
        self._pool_repository.append(chunk)
        log.debug('appended chunk to pool repository, size now {}'.format(self._pool_repository.total_bytes()))
        self._archive_service.sweep_expired()
