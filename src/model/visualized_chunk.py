
from dataclasses import dataclass
import time
from typing import List
from model.chunk import Chunk

@dataclass
class VisualizedChunk:
    chunk: Chunk
    walk1d_img: str
    walk2d_img: str

