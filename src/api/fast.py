from fastapi import FastAPI
from src.bbox import BBox, BBoxBounds
from pipelines.inference import InferencePipeline
from src.model_config import Model
from fastapi.responses import ORJSONResponse
import json


app = FastAPI()

inference = InferencePipeline(Model.path.value)


@app.post("/predict")
def inference_bbox(bboxbounds: BBoxBounds):
    bbox = BBox(bboxbounds)
    preds = json.loads(inference.run(bbox).preds.to_json())

    return ORJSONResponse(content={"status": "success", "predictions": preds})


if __name__ == "__main___":
    pass
