"""
audio_plot.py — renders raw audio samples to a base64-encoded PNG.

Kept separate from the service layer: ServeService's job is to return
data (raw bytes + audio_samples), not to know anything about how that
data gets presented. This module is a presentation-layer helper, called
from the controller.

Uses matplotlib's object-oriented Figure/FigureCanvasAgg API rather than
the global `pyplot` state machine, so concurrent requests each get their
own isolated Figure — pyplot's global state is not safe to share across
threads handling simultaneous requests.
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