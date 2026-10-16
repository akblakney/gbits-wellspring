import base64
from io import BytesIO

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend; set before importing pyplot

import matplotlib.pyplot as plt
import numpy as np

from util.visualization_utils import to_steps, apply_dark_style
from service.archive_service import ArchiveService

from model.visualized_chunk import VisualizedChunk

import logging

logger = logging.getLogger(__name__)


class VisualizeService:
    def __init__(self, archive_service: ArchiveService):
        self._archive_service = archive_service

    def visualize(self) -> VisualizedChunk:
        chunk: Chunk = self._archive_service.get_latest_chunk()
        if chunk is None:
            logger.warning("No latest chunk available")
            raise HTTPException(status_code=503, detail="Not enough entropy available, try again shortly")

        logger.info("in vis service, chunk size %s", len(chunk.data))

        img_1d = visualize_1d_walk(chunk)
        img_2d = "sdf"

        visualized_chunk = VisualizedChunk(chunk, img_1d, img_2d)


    def visualize_1d_walk(self, chunk: Chunk) -> str:

        data = chunk.data
        steps = to_steps(data)
        walk = np.cumsum(steps)

        apply_dark_style()

        fig, ax = plt.subplots(figsize=(12, 5))
        try:
            ax.plot(walk, linewidth=0.5, color="steelblue")
            ax.axhline(
                0,
                color="white",
                linewidth=0.5,
                linestyle="--",
                alpha=0.4,
            )
            ax.set_xlabel("Step")
            ax.set_ylabel("Position")
            ax.set_title(f"1D Random Walk ({len(steps):,} steps)")
            fig.tight_layout()

            # Render the figure into memory.
            buffer = BytesIO()
            fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
            buffer.seek(0)

            # Encode PNG bytes as Base64.
            return base64.b64encode(buffer.read()).decode("ascii")

        finally:
            # Important for a long-running web server.
            plt.close(fig)