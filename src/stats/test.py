import numpy as np
from scipy.stats import chisquare
from scipy.special import erfc

def test_byte_chi_square(data: np.ndarray) -> dict:
    counts = np.bincount(data, minlength=256)
    expected = len(data) / 256
    stat, p_value = chisquare(counts)
    return {
        "expected_per_bin": round(expected, 2),
        "statistic": round(float(stat), 4),
        "degrees_of_freedom": 255,
        "p_value": round(float(p_value), 4),
    }


def test_byte_entropy(data: np.ndarray) -> dict:
    counts = np.bincount(data, minlength=256)
    probs = counts / len(data)
    # Avoid log(0)
    probs = probs[probs > 0]
    entropy = float(-np.sum(probs * np.log2(probs)))
    return {
        "bits_per_byte": round(entropy, 6),
        "expected": 8.0,
        "delta": round(8.0 - entropy, 6),
    }


def test_byte_mean_std(data: np.ndarray) -> dict:
    return {
        "mean": round(float(data.mean()), 4),
        "std": round(float(data.std()), 4),
        "expected_mean": 127.5,
        "expected_std": round(float(np.sqrt((256**2 - 1) / 12)), 4),
    }


def test_serial_correlation(data: np.ndarray) -> dict:
    """Compute serial correlation coefficient between consecutive bytes."""
    x = data[:-1].astype(float)
    y = data[1:].astype(float)
    x_mean = x.mean()
    y_mean = y.mean()
    numerator = float(np.mean((x - x_mean) * (y - y_mean)))
    denominator = float(np.std(x) * np.std(y))
    coefficient = numerator / denominator if denominator > 0 else 0.0
    return {
        "coefficient": round(coefficient, 6),
        "note": "should be close to 0 for random data",
    }


def test_byte_pair_chi_square(data: np.ndarray) -> dict:
    """Chi-square test over all consecutive byte pairs (256x256 = 65536 bins)."""
    pairs = data[:-1].astype(np.uint32) * 256 + data[1:].astype(np.uint32)
    counts = np.bincount(pairs, minlength=65536)
    expected = len(pairs) / 65536
    stat, p_value = chisquare(counts)
    return {
        "num_pairs": len(pairs),
        "expected_per_bin": round(expected, 2),
        "statistic": round(float(stat), 4),
        "degrees_of_freedom": 65535,
        "p_value": round(float(p_value), 4),
    }


def test_byte_longest_run(data: np.ndarray) -> dict:
    """Find the longest run of any identical byte value."""
    # Use numpy run-length encoding
    changes = np.where(np.diff(data) != 0)[0]
    run_lengths = np.diff(np.concatenate(([-1], changes, [len(data) - 1])))
    longest = int(run_lengths.max())
    idx = int(run_lengths.argmax())
    # Reconstruct which byte value produced the longest run
    start = int(changes[idx - 1] + 1) if idx > 0 else 0
    byte_value = int(data[start])
    expected = np.log(len(data)) / np.log(256)
    return {
        "byte_value": byte_value,
        "observed_length": longest,
        "expected_length": round(expected, 2),
    }

def test_monobit(bits: np.ndarray) -> dict:
    """NIST SP 800-22 monobit test.

    Converts bits to +1/-1, computes the test statistic, and derives
    a p-value via the complementary error function.
    """
    n = len(bits)
    ones = int(bits.sum())
    zeros = n - ones
    # S_n = sum of (+1 for 1, -1 for 0)
    s_n = abs(ones - zeros)
    statistic = s_n / np.sqrt(n)
    p_value = float(erfc(statistic / np.sqrt(2)))
    return {
        "n_bits": n,
        "ones": ones,
        "zeros": zeros,
        "proportion_ones": round(ones / n, 6),
        "statistic": round(float(statistic), 6),
        "p_value": round(p_value, 6),
    }


def test_bit_runs(bits: np.ndarray) -> dict:
    """NIST SP 800-22 runs test.

    A run is a maximal sequence of consecutive identical bits.
    Tests whether the number of runs is consistent with a random sequence.
    """
    n = len(bits)
    proportion = float(bits.mean())

    # Pre-test: if proportion is too far from 0.5 the runs test is invalid
    tau = 2 / np.sqrt(n)
    if abs(proportion - 0.5) >= tau:
        return {
            "n_bits": n,
            "proportion_ones": round(proportion, 6),
            "p_value": None,
            "note": "pre-test failed: proportion of ones too far from 0.5",
        }

    # Count runs
    runs = int(np.sum(np.diff(bits) != 0)) + 1
    expected_runs = 2 * n * proportion * (1 - proportion)
    variance = 2 * np.sqrt(2 * n) * proportion * (1 - proportion)
    statistic = abs(runs - expected_runs) / variance
    p_value = float(erfc(statistic))

    return {
        "n_bits": n,
        "proportion_ones": round(proportion, 6),
        "num_runs": runs,
        "expected_runs": round(expected_runs, 2),
        "statistic": round(float(statistic), 6),
        "p_value": round(p_value, 6),
    }


def test_block_frequency(bits: np.ndarray, block_size: int = 128) -> dict:
    """NIST SP 800-22 block frequency test."""
    from scipy.special import gammaincc

    n = len(bits)
    num_blocks = n // block_size
    blocks = bits[:num_blocks * block_size].reshape(num_blocks, block_size)
    proportions = blocks.mean(axis=1)

    # NIST formula: 4 * M * sum((pi - 0.5)^2)
    chi_square = float(4 * block_size * np.sum((proportions - 0.5) ** 2))

    # NIST p-value uses incomplete gamma function
    p_value = float(gammaincc(num_blocks / 2, chi_square / 2))

    return {
        "block_size": block_size,
        "num_blocks": num_blocks,
        "chi_square": round(chi_square, 4),
        "degrees_of_freedom": num_blocks,
        "p_value": round(p_value, 6),
    }


def test_bit_longest_run(bits: np.ndarray) -> dict:
    """Find the longest run of identical bits (0 or 1)."""
    changes = np.where(np.diff(bits) != 0)[0]
    run_lengths = np.diff(np.concatenate(([-1], changes, [len(bits) - 1])))
    longest = int(run_lengths.max())
    idx = int(run_lengths.argmax())
    start = int(changes[idx - 1] + 1) if idx > 0 else 0
    bit_value = int(bits[start])
    expected = np.log2(len(bits))
    return {
        "bit_value": bit_value,
        "observed_length": longest,
        "expected_length": round(float(expected), 2),
    }
