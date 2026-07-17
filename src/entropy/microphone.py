"""Entropy source backed by a microphone via PyAudio."""

import os
import sys
import struct

import pyaudio

from bitarray import bitarray
from typing import List
import logging

from .base import EntropySource
from constants.audio import SAMPLE_RATE, CHUNK_SIZE

log = logging.getLogger(__name__)

def _suppress_stderr():
    """
    Supress pyaudio logs
    """

    class _Suppressor:
        def __enter__(self):
            self._stderr_fd = sys.stderr.fileno()
            self._saved_fd = os.dup(self._stderr_fd)
            self._devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(self._devnull, self._stderr_fd)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            os.dup2(self._saved_fd, self._stderr_fd)
            os.close(self._devnull)
            os.close(self._saved_fd)

    return _Suppressor()


class MicrophoneSource(EntropySource):
    """Reads raw 16-bit PCM audio samples from a microphone.

    `read_raw` returns a `bytes` object containing the raw byte stream
    as produced by PyAudio, where each sample is a 16-bit signed
    little-endian integer (paInt16).
    """

    def __init__(
        self,
        rate: int = SAMPLE_RATE,
        channels: int = 1,
        chunk_size: int = CHUNK_SIZE,
        input_device_index: int | None = None,
    ) -> None:
        log.debug('in microphoneSource init')
        self.rate = rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.input_device_index = input_device_index
        self.format = pyaudio.paInt16

        self._pa: pyaudio.PyAudio | None = None
        self._stream = None
        self.lsb_bits = 1
        self.interval = 1

    def open(self) -> None:
        with _suppress_stderr():
            self._pa = pyaudio.PyAudio()
            self._stream = self._pa.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=self.input_device_index,
                frames_per_buffer=self.chunk_size,
            )

    def read_raw(self, num_chunks: int = 1) -> bytes:
        log.debug('in read raw microphone')
        """Read `num_chunks` chunks of audio and return the raw bytes.

        Each chunk contains `chunk_size` samples; each sample is 2 bytes
        (16-bit signed integer).
        """
        if self._stream is None:
            raise RuntimeError("MicrophoneSource is not open. Call open() first.")

        data = bytearray()
        for _ in range(num_chunks):
            data.extend(self._stream.read(self.chunk_size, exception_on_overflow=False))
        return bytes(data)

    def standardize(self, raw: bytes) -> List[int]:
        if len(raw) % 2 != 0:
            raise ValueError(
                f"Raw audio data length must be a multiple of 2 bytes, got {len(raw)}"
            )

        num_samples = len(raw) // 2
        return list(struct.unpack(f"<{num_samples}h", raw))

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pa is not None:
            self._pa.terminate()
            self._pa = None

    def extract(self, values: List[int]) -> bitarray:
        bits = bitarray()
        mask = (1 << self.lsb_bits) - 1 # mask with lsb_bits lowest bits

        for i in range(0, len(values), self.interval):
            low_bits = values[i] & mask
            for j in range(self.lsb_bits - 1, -1, -1):
                bits.append((low_bits >> j) & 1)

        return bits