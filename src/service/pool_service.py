
from repository.pool_repository import PoolRepository

class PoolService:
    def __init__(self, pool_repository: PoolRepository):
        self._pool_repository = pool_repository

    def num_chunks(self):
        return self._pool_repository.size()

    def num_bytes(self):
        return self._pool_repository.total_bytes()