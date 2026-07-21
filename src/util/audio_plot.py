"""
audio_plot.py — renders raw audio samples to a base64-encoded PNG.
"""

import base64
import io
from typing import Sequence

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg


def render_audio_plot_base64(audio_samples: Sequence[int], dpi: int = 100) -> str:
    """
    Render audio_samples as a waveform plot and return it as a
    base64-encoded PNG string (no data: URI prefix — caller decides
    how to embed it).
    """
    fig = Figure(figsize=(6, 2.5), dpi=dpi)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)

    ax.plot(audio_samples, linewidth=0.6)
    ax.set_title("Raw microphone samples")
    ax.set_xlabel("Sample index")
    ax.set_ylabel("Amplitude")
    fig.tight_layout()

    buf = io.BytesIO()
    canvas.print_png(buf)
    buf.seek(0)

    return base64.b64encode(buf.read()).decode("ascii")