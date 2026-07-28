"""
analyze_audio_source.py — standalone diagnostic tool for evaluating a
microphone (or any 3.5mm audio input) as a hardware entropy source.

Fully self-contained: does NOT depend on the gbits/Wellspring codebase.
Copy this single file to any machine to test a candidate mic before
ever wiring it into the real pipeline.

Records a short clip, then reports:
  - Signal level / clipping stats
  - LSB bias, Shannon entropy, and min-entropy (the bit the real
    generator actually extracts)
  - Low-byte (8-bit) entropy and a uniformity chi-square check
  - Estimated Von Neumann discard rate on the LSB stream
  - Autocorrelation across a range of lags, with explicit callouts at
    the 50Hz/60Hz mains-hum lags
  - FFT power spectrum peak-finding, to catch ANY periodic
    contamination, not just mains hum specifically

Usage:
    python analyze_audio_source.py --list-devices
    python analyze_audio_source.py --label old_broken_mic --duration 10
    python analyze_audio_source.py --label sealed_capsule_v1 --device-index 2

Requires: numpy, pyaudio (pip install numpy pyaudio)
"""

import argparse
import math
import struct
import sys
import time
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE_DEFAULT = 44100
MAINS_HZ_CANDIDATES = [50.0, 60.0]  # check both -- report which region you're in


# --------------------------------------------------------------------------
# Capture (isolated from analysis logic below, so analysis can be tested
# independently of having real audio hardware / pyaudio available).
# --------------------------------------------------------------------------

def _require_pyaudio():
    try:
        import pyaudio
        return pyaudio
    except ImportError:
        print("Error: pyaudio is not installed.\n"
              "Install it with:  pip install pyaudio\n"
              "(On Linux you may first need: sudo apt install portaudio19-dev)",
              file=sys.stderr)
        sys.exit(1)


def list_devices() -> None:
    pyaudio = _require_pyaudio()
    pa = pyaudio.PyAudio()
    try:
        print(f"{'Index':<7}{'Name':<48}{'Max input channels'}")
        print("-" * 70)
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                print(f"{i:<7}{info['name']:<48}{info['maxInputChannels']}")
    finally:
        pa.terminate()


def record_audio(duration_seconds: float, rate: int, channels: int,
                  chunk_size: int, device_index: int | None) -> np.ndarray:
    pyaudio = _require_pyaudio()

    pa = pyaudio.PyAudio()
    try:
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=chunk_size,
        )
        try:
            print(f"Recording {duration_seconds:.1f}s at {rate}Hz... ", end="", flush=True)
            n_chunks = int(rate / chunk_size * duration_seconds)
            frames = []
            for _ in range(n_chunks):
                frames.append(stream.read(chunk_size, exception_on_overflow=False))
            print("done.")
        finally:
            stream.stop_stream()
            stream.close()
    finally:
        pa.terminate()

    raw = b"".join(frames)
    num_samples = len(raw) // 2
    samples = struct.unpack(f"<{num_samples}h", raw)
    return np.array(samples, dtype=np.int16)


def save_wav(path: Path, samples: np.ndarray, rate: int, channels: int) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(channels)
        f.setsampwidth(2)  # 16-bit
        f.setframerate(rate)
        f.writeframes(samples.astype(np.int16).tobytes())


# --------------------------------------------------------------------------
# Analysis (pure functions, testable with synthetic data)
# --------------------------------------------------------------------------

def level_stats(samples: np.ndarray) -> dict:
    n = len(samples)
    abs_samples = np.abs(samples.astype(np.int64))
    full_scale = 32767
    near_clip_threshold = int(full_scale * 0.98)
    n_near_clip = int(np.sum(abs_samples >= near_clip_threshold))

    return {
        "num_samples": n,
        "min": int(samples.min()),
        "max": int(samples.max()),
        "mean": float(samples.mean()),
        "std": float(samples.std()),
        "rms": float(np.sqrt(np.mean(samples.astype(np.float64) ** 2))),
        "peak_pct_full_scale": float(abs_samples.max() / full_scale * 100),
        "pct_samples_near_clipping": float(n_near_clip / n * 100),
    }


def extract_lsb(samples: np.ndarray) -> np.ndarray:
    """Bit 0 of each sample, as a 0/1 uint8 array -- matches lsb_bits=1 in the real extractor."""
    return (samples.astype(np.uint16) & 1).astype(np.uint8)


def shannon_entropy_bits(bit_array: np.ndarray) -> float:
    """Shannon entropy of a binary sequence, in bits (max 1.0)."""
    n = len(bit_array)
    p1 = np.sum(bit_array) / n
    p0 = 1 - p1
    h = 0.0
    for p in (p0, p1):
        if p > 0:
            h -= p * math.log2(p)
    return h


def min_entropy_bits(bit_array: np.ndarray) -> float:
    """
    Min-entropy: -log2(max probability). The conservative,
    security-relevant measure -- bounds how predictable the SINGLE most
    likely outcome is, rather than averaging over all outcomes the way
    Shannon entropy does. Max value 1.0 for a fair coin.
    """
    n = len(bit_array)
    p1 = np.sum(bit_array) / n
    p_max = max(p1, 1 - p1)
    return -math.log2(p_max) if p_max > 0 else 0.0


def low_byte_stats(samples: np.ndarray) -> dict:
    """Entropy/uniformity of the low 8 bits of each sample, as a symbol 0-255."""
    low_bytes = (samples.astype(np.uint16) & 0xFF).astype(np.uint8)
    n = len(low_bytes)
    counts = np.bincount(low_bytes, minlength=256)
    probs = counts / n

    shannon_h = -np.sum(probs[probs > 0] * np.log2(probs[probs > 0]))
    min_h = -math.log2(probs.max()) if probs.max() > 0 else 0.0

    expected = n / 256
    chi2_stat = float(np.sum((counts - expected) ** 2 / expected))
    df = 255
    p_value = chi2_pvalue_wilson_hilferty(chi2_stat, df)

    return {
        "shannon_entropy_bits": float(shannon_h),
        "min_entropy_bits": float(min_h),
        "chi2_statistic": chi2_stat,
        "chi2_df": df,
        "chi2_p_value": p_value,
    }


def chi2_pvalue_wilson_hilferty(chi2_stat: float, df: int) -> float:
    """
    Approximate upper-tail p-value for a chi-square statistic, via the
    Wilson-Hilferty cube-root normal approximation. Avoids a scipy
    dependency for one calculation -- accurate to within a percent or
    so for df this large, which is plenty for a "does this look
    roughly uniform" diagnostic (not a precision statistical claim).
    """
    if df <= 0:
        return float("nan")
    z = (((chi2_stat / df) ** (1 / 3)) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
    # upper-tail p-value from standard normal z
    return 0.5 * math.erfc(z / math.sqrt(2))


def von_neumann_discard_rate(bit_array: np.ndarray) -> dict:
    """
    Estimated discard rate if this LSB stream were run through standard
    Von Neumann whitening: non-overlapping pairs, discard 00/11, keep
    01->0 and 10->1. ~50% discard is what you'd expect from a
    near-full-entropy bit (matches what's discussed as the real
    generator's observed behavior); much higher discard indicates bias.
    """
    n_pairs = len(bit_array) // 2
    pairs = bit_array[: n_pairs * 2].reshape(n_pairs, 2)
    matched = pairs[:, 0] == pairs[:, 1]
    n_discarded = int(np.sum(matched))
    n_kept = n_pairs - n_discarded
    return {
        "pairs_total": n_pairs,
        "pairs_discarded": n_discarded,
        "pairs_kept": n_kept,
        "discard_rate_pct": float(n_discarded / n_pairs * 100) if n_pairs else 0.0,
    }


def autocorrelation_fft(x: np.ndarray, max_lag: int) -> np.ndarray:
    """
    Full autocorrelation via the Wiener-Khinchin theorem (FFT of the
    signal, magnitude-squared, inverse FFT) -- much faster than a naive
    O(N * max_lag) loop for the sample counts involved here (hundreds
    of thousands of samples). Returns normalized values (lag 0 = 1.0).
    """
    x = x.astype(np.float64)
    x = x - x.mean()
    n = len(x)

    # zero-pad to avoid circular-correlation wraparound artifacts
    padded_len = 1
    while padded_len < 2 * n:
        padded_len *= 2

    fft_x = np.fft.rfft(x, n=padded_len)
    power = fft_x * np.conj(fft_x)
    autocorr_full = np.fft.irfft(power, n=padded_len)[:n]

    if autocorr_full[0] == 0:
        return np.zeros(max_lag + 1)
    normalized = autocorr_full / autocorr_full[0]
    return normalized[: max_lag + 1]


def autocorrelation_report(x: np.ndarray, max_lag: int, rate: int) -> dict:
    autocorr = autocorrelation_fft(x, max_lag)
    n = len(x)

    # rough 95% "white noise" significance band: +/- 1.96/sqrt(n)
    threshold = 1.96 / math.sqrt(n)

    # exclude lag 0 (always 1.0 by definition) when finding the max
    lags_to_check = autocorr[1:]
    peak_lag = int(np.argmax(np.abs(lags_to_check))) + 1
    peak_value = float(lags_to_check[peak_lag - 1])

    mains_lags = {}
    for hz in MAINS_HZ_CANDIDATES:
        lag = round(rate / hz)
        if lag <= max_lag:
            mains_lags[f"{hz:.0f}Hz (lag {lag})"] = float(autocorr[lag])
    
    lower_lags = {}
    for lag in [1, 2, 4, 8, 16, 32, 64, 128]:
        if lag <= max_lag:
            lower_lags['lag = {}'.format(lag)] = float(autocorr[lag])

    return {
        "threshold_95pct": threshold,
        "lower_lags": lower_lags,
        "peak_lag": peak_lag,
        "peak_value": peak_value,
        "peak_exceeds_threshold": abs(peak_value) > threshold,
        "mains_lags": mains_lags,
    }


def spectral_peaks(samples: np.ndarray, rate: int, top_n: int = 5) -> tuple[list[dict], float]:
    """
    FFT power spectrum peak-finding. Catches ANY dominant periodic
    component (not just mains hum specifically) -- e.g. switching
    power supply noise, coil whine, etc. Reports frequency and how many
    times above the spectrum's median power that peak is.

    Returns (peaks, dominance_threshold). The threshold scales with the
    number of frequency bins actually searched, via extreme-value
    theory: under pure white noise, each periodogram bin is
    approximately Exponentially distributed relative to its mean, and
    the expected MAXIMUM among M such bins grows like ln(M) + gamma
    (Euler-Mascheroni). A fixed threshold (e.g. always "20x median")
    would false-flag pure noise more often at higher sample counts
    (more bins checked = higher expected max by chance alone, same
    multiple-comparisons effect as the autocorrelation lag check) --
    scaling the threshold with bin count keeps the false-positive rate
    roughly constant regardless of recording length.
    """
    x = samples.astype(np.float64)
    x = x - x.mean()
    n = len(x)

    window = np.hanning(n)
    spectrum = np.abs(np.fft.rfft(x * window)) ** 2
    freqs = np.fft.rfftfreq(n, d=1.0 / rate)

    # ignore DC and near-DC
    min_bin = max(1, int(1.0 / (rate / n)))
    spectrum_search = spectrum[min_bin:]
    freqs_search = freqs[min_bin:]

    median_power = np.median(spectrum_search)
    if median_power == 0:
        return [], float("inf")

    num_bins = len(spectrum_search)
    euler_mascheroni = 0.5772156649
    expected_max_ratio = math.log(num_bins) + euler_mascheroni
    # safety margin above the pure-chance expectation, not a tight bound
    dominance_threshold = 2.0 * expected_max_ratio

    # find local peaks: a bin higher than both neighbors
    peak_indices = []
    for i in range(1, len(spectrum_search) - 1):
        if spectrum_search[i] > spectrum_search[i - 1] and spectrum_search[i] > spectrum_search[i + 1]:
            peak_indices.append(i)

    peak_indices.sort(key=lambda i: spectrum_search[i], reverse=True)

    results = []
    for i in peak_indices[:top_n]:
        results.append({
            "frequency_hz": float(freqs_search[i]),
            "power_ratio_vs_median": float(spectrum_search[i] / median_power),
        })
    return results, dominance_threshold


# --------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------

def build_report(label: str, rate: int, level: dict, lsb: dict, low_byte: dict,
                  vn: dict, autocorr_raw: dict, autocorr_lsb: dict,
                  spectral: list[dict], spectral_threshold: float) -> str:
    out = []
    out.append("=" * 72)
    out.append(f"Audio entropy source diagnostic: {label}")
    out.append("=" * 72)
    out.append(f"Sample rate:      {rate} Hz")
    out.append(f"Samples analyzed: {level['num_samples']:,}")
    out.append("")

    out.append("-" * 72)
    out.append("Signal level")
    out.append("-" * 72)
    out.append(f"  Range:                 {level['min']} to {level['max']}")
    out.append(f"  Mean / Std:            {level['mean']:.2f} / {level['std']:.2f}")
    out.append(f"  RMS:                   {level['rms']:.2f}")
    out.append(f"  Peak (% of full scale): {level['peak_pct_full_scale']:.2f}%")
    out.append(f"  Samples near clipping: {level['pct_samples_near_clipping']:.3f}%")
    if level["pct_samples_near_clipping"] > 1.0:
        out.append("  ! WARNING: significant clipping detected -- reduce input gain")
    if level["rms"] < 50:
        out.append("  ! Very low signal level -- may not provide enough amplitude to")
        out.append("    dither the LSB reliably (see LSB entropy below)")
    out.append("")

    out.append("-" * 72)
    out.append("LSB (bit 0)")
    out.append("-" * 72)
    out.append(f"  Proportion of 1s:      {lsb['p1']:.6f}")
    out.append(f"  Shannon entropy:       {lsb['shannon_entropy_bits']:.5f} bits  (max: 1.0)")
    out.append(f"  Min-entropy:           {lsb['min_entropy_bits']:.5f} bits  (max: 1.0)")
    out.append("")

    out.append("-" * 72)
    out.append("Low byte (bits 0-7)")
    out.append("-" * 72)
    out.append(f"  Shannon entropy:       {low_byte['shannon_entropy_bits']:.4f} bits  (max: 8.0)")
    out.append(f"  Min-entropy:           {low_byte['min_entropy_bits']:.4f} bits  (max: 8.0)")
    out.append(f"  Uniformity chi-square: {low_byte['chi2_statistic']:.2f}  (df={low_byte['chi2_df']})")
    out.append(f"  Uniformity p-value:    {low_byte['chi2_p_value']:.4f}")
    out.append("")

    out.append("-" * 72)
    out.append("Estimated Von Neumann discard rate (on LSB stream)")
    out.append("-" * 72)
    out.append(f"  Pairs total:           {vn['pairs_total']:,}")
    out.append(f"  Pairs discarded:       {vn['pairs_discarded']:,}  ({vn['discard_rate_pct']:.2f}%)")
    out.append(f"  Pairs kept (output):   {vn['pairs_kept']:,}")
    out.append("")

    for title, ac in [("Autocorrelation -- raw samples", autocorr_raw),
                       ("Autocorrelation -- LSB stream", autocorr_lsb)]:
        out.append("-" * 72)
        out.append(title)
        out.append("-" * 72)
        out.append(f"  95% significance threshold: +/- {ac['threshold_95pct']:.5f}")
        out.append(f"  Largest |autocorrelation|:  {ac['peak_value']:.5f} at lag {ac['peak_lag']}"
                    + ("  <-- EXCEEDS THRESHOLD" if ac["peak_exceeds_threshold"] else ""))
        for label, value in ac['lower_lags'].items():
            flag = "  <-- EXCEEDS THRESHOLD" if abs(value) > ac["threshold_95pct"] else ""
            out.append(f"  {label}: {value:.5f}{flag}")

        for label_hz, value in ac["mains_lags"].items():
            flag = "  <-- EXCEEDS THRESHOLD" if abs(value) > ac["threshold_95pct"] else ""
            out.append(f"  Mains hum check, {label_hz}: {value:.5f}{flag}")
        out.append("")

    out.append("-" * 72)
    out.append("Spectral peaks (top, raw samples)")
    out.append("-" * 72)
    out.append(f"  Dominance threshold: {spectral_threshold:.1f}x median (scales with recording length)")
    if not spectral:
        out.append("  (none found)")
    else:
        for p in spectral:
            flag = "  <-- notably dominant" if p["power_ratio_vs_median"] > spectral_threshold else ""
            out.append(f"  {p['frequency_hz']:8.2f} Hz   {p['power_ratio_vs_median']:8.1f}x median power{flag}")
    out.append("")
    out.append("=" * 72)

    return "\n".join(out)


def analyze(samples: np.ndarray, rate: int, max_lag: int, label: str) -> str:
    level = level_stats(samples)

    lsb_bits = extract_lsb(samples)
    lsb = {
        "p1": float(np.sum(lsb_bits) / len(lsb_bits)),
        "shannon_entropy_bits": shannon_entropy_bits(lsb_bits),
        "min_entropy_bits": min_entropy_bits(lsb_bits),
    }

    low_byte = low_byte_stats(samples)
    vn = von_neumann_discard_rate(lsb_bits)

    autocorr_raw = autocorrelation_report(samples, max_lag, rate)
    # map LSB bits to +1/-1 for a meaningful (non-degenerate) autocorrelation
    lsb_signed = (lsb_bits.astype(np.float64) * 2) - 1
    autocorr_lsb = autocorrelation_report(lsb_signed, max_lag, rate)

    spectral, spectral_threshold = spectral_peaks(samples, rate)

    return build_report(label, rate, level, lsb, low_byte, vn, autocorr_raw, autocorr_lsb, spectral, spectral_threshold)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Diagnose a microphone's suitability as an entropy source")
    parser.add_argument("--list-devices", action="store_true", help="List available input devices and exit")
    parser.add_argument("--duration", type=float, default=10.0, help="Recording duration in seconds (default: 10)")
    parser.add_argument("--rate", type=int, default=SAMPLE_RATE_DEFAULT, help="Sample rate (default: 44100)")
    parser.add_argument("--channels", type=int, default=1, help="Channels (default: 1)")
    parser.add_argument("--chunk-size", type=int, default=1024, help="Read chunk size (default: 1024)")
    parser.add_argument("--device-index", type=int, default=None, help="Input device index (see --list-devices)")
    parser.add_argument("--max-lag", type=int, default=2000, help="Max autocorrelation lag to check (default: 2000)")
    parser.add_argument("--label", type=str, default=None, help="Label for this run (used in output filenames)")
    parser.add_argument("--output-dir", type=str, default="./audio_analysis_output",
                         help="Directory to save the WAV recording + report")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_devices:
        list_devices()
        return

    label = args.label or f"session_{int(time.time())}"
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    samples = record_audio(args.duration, args.rate, args.channels, args.chunk_size, args.device_index)

    wav_path = output_dir / f"{label}.wav"
    save_wav(wav_path, samples, args.rate, args.channels)
    print(f"Saved recording: {wav_path}")

    report = analyze(samples, args.rate, args.max_lag, label)
    print("\n" + report)

    report_path = output_dir / f"{label}_report.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nSaved report: {report_path}")


if __name__ == "__main__":
    main()
