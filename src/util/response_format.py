from model.chunk import Chunk
from datetime import datetime
from stats.test import test_monobit
import numpy as np

def chunk_dict(chunk: Chunk):
    return {
        'data': chunk.data.hex(),
        'created_at': datetime.fromtimestamp(chunk.created_at).isoformat(),
        'pairs_discarded': chunk.pairs_discarded,
        'pairs_kept': chunk.pairs_kept,
        'stats': {
            'monobit': test_monobit(np.frombuffer(chunk.data, dtype=np.uint8))
        }
    }
