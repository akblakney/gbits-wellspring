from dataclasses import dataclass
from typing import List

@dataclass
class BitsResponse:
    data: bytes
    audio_samples: List[int]
    pairs_discarded: int
    pairs_kept: int
    total_chunks: int
