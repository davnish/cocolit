from fastapi import FastAPI
from src.data_struct.bbox import BBox, BBoxBounds
from pipelines.inference import InferencePipeline
from fastapi.responses import ORJSONResponse
import json
import yaml

def read_config()-> dict:
    """Read the config file and return the config dictionary."""
    with open("configs/config.yml", "r") as f:
        config = yaml.safe_load(f)
        return config
    

config = read_config()

app = FastAPI()

inference = InferencePipeline(config['model']['path'])

@app.post("/predict")
def inference_bbox(bboxbounds: BBoxBounds) -> ORJSONResponse:
    bbox = BBox(bboxbounds)
    preds = json.loads(inference.run(bbox).preds.to_json())
    return ORJSONResponse(content={"status": "success", "predictions": preds})


if __name__ == "__main___":

    pass
