"""
Generator — the production loop.

STUB: uses Python's built-in `random` module to produce bytes on an
interval, standing in for real microphone-noise entropy capture. Runs
as a background thread so the API server can serve requests concurrently.

Real mic capture + von Neumann extraction will replace
_generate_raw_bytes() later without changing the run loop's shape.
"""

import logging
import random
import threading
import time

from service.generation_service import GenerationService
from config import config
from entropy.base import EntropySource
from extract.von_neumann import VonNeumannExtractor
from model.chunk import Chunk

log = logging.getLogger(__name__)


class Generator:
    def __init__(self, generation_service: GenerationService, entropy_source: EntropySource, von_neumann_extractor: VonNeumannExtractor ):
        self._generation_service = generation_service
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.entropy_source = entropy_source
        self.von_neumann_extractor = von_neumann_extractor

    def start(self) -> None:
        """Start the generation loop in a background thread."""
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        log.info("Generator started")

    def stop(self) -> None:
        """Signal the generation loop to stop and wait for it to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        log.info("Generator stopped")

    def run(self) -> None:
        """Main loop: produce a chunk of bytes every GENERATOR_INTERVAL_SECONDS."""
        self.entropy_source.open()
        log.info("Entropy source opened")
        try:
            while not self._stop_event.is_set():
                try:
                    chunk = self._generate_raw_bytes()
                    self._generation_service.ingest(chunk)
                except Exception:
                    log.error("Unexpected error in generator loop -- continuing", exc_info=True)
        finally:
            self.entropy_source.close()
            log.info("Entropy source closed")

    def _generate_raw_bytes(self) -> Chunk:
        log.debug('in generate')
        raw = self.entropy_source.read_raw()
        values = self.entropy_source.standardize(raw)
        bits = self.entropy_source.extract(values)
        data = self.von_neumann_extractor.extract(bits)
        discarded = self.von_neumann_extractor.pairs_discarded
        kept = self.von_neumann_extractor.pairs_output
        return Chunk.now(data=data, audio_samples=values, pairs_discarded=discarded, pairs_kept=kept)