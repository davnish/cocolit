import tempfile
from pathlib import Path
from dataclasses import dataclass, field
import shutil


@dataclass
class GetPath:
    temp_name: str = "image"
    dir: Path = field(init=False)
    image_path: Path = field(init=False)
    patched: Path = field(init=False)

    def __post_init__(self) -> None:
        dir = Path("data")
        dir.mkdir(parents=True, exist_ok=True)

        self.dir = Path(tempfile.mkdtemp(dir=dir))
        self.image_path = self.dir / f"{self.temp_name}.tif"
        self.patched = self.dir / "patched"
        self.patched.mkdir(parents=True, exist_ok=True)

    def rm(self) -> None:
        shutil.rmtree(self.dir)
