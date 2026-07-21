import collections
import threading

from model.chunk import Chunk

class PoolRepository:
    def __init__(self):
        self._queue = collections.deque()
        self._lock = threading.Lock()

    def append(self, chunk: Chunk) -> None:
        """Add a chunk to the back of the queue."""
        with self._lock:
            self._queue.append(chunk)

    def peek_front(self) -> Chunk | None:
        """Look at the front chunk without removing it. None if empty."""
        with self._lock:
            if not self._queue:
                return None
            return self._queue[0]

    def pop_front(self) -> Chunk | None:
        """Remove and return the front chunk. None if empty."""
        with self._lock:
            if not self._queue:
                return None
            return self._queue.popleft()

    def size(self) -> int:
        """Number of chunks currently in the pool (for logging/monitoring)."""
        with self._lock:
            return len(self._queue)

    def total_bytes(self) -> int:
        """Total bytes currently held across all chunks (for logging/monitoring)."""
        with self._lock:
            return sum(len(c) for c in self._queue)
