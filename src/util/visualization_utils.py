import numpy as np

def to_uint8(data: bytes | np.ndarray) -> np.ndarray:
    """Convert bytes or ndarray to uint8 array."""
    if isinstance(data, bytes):
        return np.frombuffer(data, dtype=np.uint8)
    return np.asarray(data, dtype=np.uint8)


def to_bits(data: bytes | np.ndarray) -> np.ndarray:
    """Unpack bytes to a flat bit array (0s and 1s)."""
    return np.unpackbits(to_uint8(data))


def to_steps(data: bytes | np.ndarray) -> np.ndarray:
    """Convert bits to +1/-1 steps for random walk."""
    return to_bits(data).astype(np.int8) * 2 - 1 


def to_coordinates(data: bytes | np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Split uint8 array into interleaved x and y coordinate arrays."""
    arr = to_uint8(data)
    return arr[0::2].astype(float), arr[1::2].astype(float)

def apply_dark_style() -> None:
    """Apply a dark theme to all subsequent matplotlib plots."""
    import matplotlib.pyplot as plt 
    plt.style.use("dark_background")