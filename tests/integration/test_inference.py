from src.data_struct.bbox import BBox
from pipelines.inference import InferencePipeline
from pathlib import Path
import yaml

def read_config() -> dict:
    with open("configs/config.yml", "r") as f:
        config = yaml.safe_load(f)
        return config

config = read_config()

def test_inference() -> None:
    data = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [80.020219, 7.809309],
                    [80.020219, 7.810361],
                    [80.021667, 7.810361],
                    [80.021667, 7.809309],
                    [80.020219, 7.809309],
                ]
            ],
        },
    }
    bbox = BBox(data)
    inference = InferencePipeline(Path(config['model']['path']))
    bbox = inference.run(bbox)
    assert len(bbox.preds) == 158
