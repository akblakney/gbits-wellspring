import numpy as np
from util.byte import unpack_bits

from stats.test import (
    test_byte_chi_square,
    test_byte_entropy,
    test_byte_mean_std,
    test_serial_correlation,
    test_byte_pair_chi_square,
    test_byte_longest_run,
    test_monobit,
    test_bit_runs,
    test_block_frequency,
    test_bit_longest_run,
)

def compute_stats(data: np.ndarray, label: str) -> dict:
    """Run all statistical tests on a uint8 array and return as a dict."""
    bits = unpack_bits(data)
    return {
        "label": label,
        "total_bytes": len(data),
        "total_bits": len(bits),
        "byte_level": {
            "chi_square": test_byte_chi_square(data),
            "entropy": test_byte_entropy(data),
            "mean_std": test_byte_mean_std(data),
            "serial_correlation": test_serial_correlation(data),
            "byte_pair_chi_square": test_byte_pair_chi_square(data),
            "longest_run": test_byte_longest_run(data),
        },
        "bit_level": {
            "monobit": test_monobit(bits),
            "runs": test_bit_runs(bits),
            "block_frequency": test_block_frequency(bits),
            "longest_run": test_bit_longest_run(bits),
        },
    }
