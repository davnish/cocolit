from enum import Enum

from pathlib import Path

class Model(Enum):
    path : Path = Path("models/train/weights/best.onnx")