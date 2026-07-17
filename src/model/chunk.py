"""
Shared data model for a chunk of generated random bytes.

A Chunk is the unit the pool operates on: one batch of bytes produced by
a single generation cycle, tagged with when it was created. Later on this
will also carry von-Neumann-extractor metadata (raw sample size, discard
count, etc.) — omitted for now per the barebones approach.
"""

from dataclasses import dataclass
import time
from typing import List


@dataclass
class Chunk:
    data: bytes
    created_at: float  # unix timestamp, from time.time()
    audio_samples: List[int]
    pairs_discarded: int = None
    pairs_kept: int = None

    @staticmethod
    def now(data: bytes, audio_samples: List[int], pairs_discarded=None, pairs_kept=None) -> "Chunk":
        """Convenience constructor: build a Chunk timestamped at creation time."""
        return Chunk(data=data, created_at=time.time(), audio_samples=audio_samples, pairs_discarded=pairs_discarded, pairs_kept=pairs_kept)

    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def __len__(self) -> int:
        return len(self.data)
