from dataclasses import dataclass, field
import tempfile
from pathlib import Path


@dataclass(frozen=True)
class GetPath:
    temp_name: str = 'image'
    dir: Path = field(init=False)
    image_path: Path = field(init=False)
    txt_path: Path = field(init=False)

    def __post_init__(self):
        tmp_dir = Path(tempfile.mkdtemp(dir = 'data/'))
        object.__setattr__(self, 'dir', tmp_dir)
        object.__setattr__(self, 'image_path', self.dir / f"{self.temp_name}.tif")
        object.__setattr__(self, 'txt_path', self.dir / f"predict/labels/{self.temp_name}.txt")

@dataclass
class bbox:
    pass
    




temp = GetPath()
temp2 = GetPath()
print(temp.dir)
print(temp2)
