import asyncio
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

@app.get("/")
def read_root():
    return {"message": "Welcome to the Inference API"}

@app.post("/predict")
async def inference_bbox(bboxbounds: BBoxBounds) -> ORJSONResponse:
    bbox = BBox(bboxbounds)
    bbox = await asyncio.to_thread(inference.run, bbox) # Run in a separate thread to avoid blocking event loop
    preds = json.loads(bbox.preds.to_json())
    return ORJSONResponse(content={"status": "success", "predictions": preds})

@app.get("/health")
def health_check():
    return ORJSONResponse(content={"status": "ok"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("inference:app", host="127.0.0.1", port=8000, reload=True)
