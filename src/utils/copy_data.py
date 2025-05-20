import shutil
from pathlib import Path


def copy_data(dataset: dict, cfg: dict) -> None:
    path = Path(cfg.dataPath)

    for data in dataset:
        data_type = "x" if "x" in data else "y"
        _data = data.split(data_type)[0]
        data_type = "images" if data_type == "x" else "labels"

        path = path / {_data} / {data_type}
        path.mkdir(parents=True, exist_ok=True)

        for file in dataset[data]:
            shutil.copy(file, path)
