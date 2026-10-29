from model.chunk import Chunk

def chunk_dict(chunk: Chunk):
    return {
        'data': chunk.data.hex(),
        'created_at': chunk.created_at,
        'pairs_discarded': chunk.pairs_discarded,
        'pairs_kept': chunk.pairs_kept
    }
