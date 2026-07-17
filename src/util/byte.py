import numpy as np

def unpack_bits(data: np.ndarray) -> np.ndarray:
    """Unpack uint8 array to a bit array (0s and 1s)."""
    return np.unpackbits(data)
