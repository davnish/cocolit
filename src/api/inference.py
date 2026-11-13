import asyncio
import hmac
import os

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from src.data_struct.bbox import BBox, BBoxBounds
from pipelines.inference import InferencePipeline
from fastapi.responses import ORJSONResponse
from src.exceptions.exceptions import BBoxTooBig, BBoxTooSmall
from src.telemetry import setup_telemetry
import yaml

def read_config()-> dict:
    """Read the config file and return the config dictionary."""
    with open("configs/config.yml", "r") as f:
        config = yaml.safe_load(f)
        return config

config = read_config()

app = FastAPI()
# No-op unless OTEL_EXPORTER_OTLP_ENDPOINT is set (see src/telemetry.py).
setup_telemetry(app, "cocolit-inference")

# Set on public deployments (Cloud Run); the in-cluster service can leave it unset.
API_KEY = os.environ.get("INFERENCE_API_KEY") or None


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if API_KEY and not hmac.compare_digest(x_api_key or "", API_KEY):
        raise HTTPException(status_code=401, detail="invalid API key")


@app.exception_handler(BBoxTooBig)
@app.exception_handler(BBoxTooSmall)
async def bbox_invalid(request: Request, exc: BBoxTooBig | BBoxTooSmall) -> ORJSONResponse:
    return ORJSONResponse(status_code=422, content={"detail": exc.message})

inference = InferencePipeline(
    config['model']['path'],
    tile_workers=config.get('inference', {}).get('tile_workers', 16),
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Inference API"}

@app.post("/predict", dependencies=[Depends(require_api_key)])
async def inference_bbox(bboxbounds: BBoxBounds) -> ORJSONResponse:
    bbox = BBox(bboxbounds)
    bbox = await asyncio.to_thread(inference.run, bbox) # Run in a separate thread to avoid blocking event loop
    # With no detections this is an empty FeatureCollection.
    return ORJSONResponse(
        content={"status": "success", "predictions": bbox.preds.to_geojson()}
    )

@app.get("/health")
def health_check():
    return ORJSONResponse(content={"status": "ok"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("inference:app", host="127.0.0.1", port=8000, reload=True)
