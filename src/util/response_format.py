from model.chunk import Chunk
from datetime import datetime
from stats.test import test_monobit
from stats.summary import compute_stats
import numpy as np

def chunk_dict(chunk: Chunk):
    nparray = np.frombuffer(chunk.data, dtype=np.uint8)

    return {
        'data': chunk.data.hex(),
        'created_at': datetime.fromtimestamp(chunk.created_at).isoformat(),
        'pairs_discarded': chunk.pairs_discarded,
        'pairs_kept': chunk.pairs_kept,
        'stats': compute_stats(nparray, 'chunk_stats')
    }
