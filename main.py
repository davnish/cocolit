import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yaml
from configs.logger import setup_logger, get_smtp_logger
from src.database.connection import engine
from src.dal.preds import preds_bbox_to_database, read_data
import os
import requests
import geopandas as gpd
from src.data_struct.bbox import BBox
from src.exceptions.exceptions import BBoxTooBig, BBoxTooSmall
from src.inference_router import InferenceRouter
import logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    if engine is not None:
        # Idempotent: creates missing tables only (fresh databases, e.g. a new cluster).
        from src.database.init_db import create_db
        try:
            await asyncio.to_thread(create_db, engine)
        except Exception:
            logging.getLogger("main").exception("could not create database tables")
    yield


app = FastAPI(title="Cocolit API", lifespan=lifespan)

def read_config() -> dict:
    with open("configs/config.yml", "r") as f:
        return yaml.safe_load(f)

config = read_config()
logger = setup_logger("main", "main.log")

try:
    smtp_logger = get_smtp_logger("main_SMTP")
except Exception as e:
    logger.fatal(f"SMTP Logger not working: {e}")
    smtp_logger = logger

# Define Request model for Inference
class InferenceRequest(BaseModel):
    type: str
    geometry: dict
    properties: dict

_router: InferenceRouter | None = None


def get_router() -> InferenceRouter:
    global _router
    if _router is None:
        url = os.environ.get("INFERENCE_URL")
        if not url:
            raise ValueError("INFERENCE_URL not set in environment")
        _router = InferenceRouter(
            local_url=url,
            overflow_url=os.environ.get("INFERENCE_OVERFLOW_URL") or None,
            api_key=os.environ.get("INFERENCE_API_KEY") or None,
            max_local=int(os.environ.get("INFERENCE_MAX_LOCAL", "1")),
        )
    return _router


def inference_request(bbox: BBox) -> tuple[gpd.GeoDataFrame, str]:
    body, backend = get_router().predict(bbox.to_dict())
    features = body["predictions"]["features"]
    if not features:
        # from_features([]) has no geometry column and raises when given a CRS.
        return gpd.GeoDataFrame({"conf": []}, geometry=gpd.GeoSeries([], crs="EPSG:3857")), backend
    return gpd.GeoDataFrame.from_features(features, crs="EPSG:3857"), backend

@app.post("/api/inference")
async def run_inference(req: InferenceRequest, response: Response):
    try:
        # Reconstruct drawing dictionary format that map_ui expected
        drawing = {
            "type": req.type,
            "geometry": req.geometry,
            "properties": req.properties
        }
        
        bbox = BBox(drawing)
        bbox.valid_bbox()  # reject before spending a (possibly Cloud Run) inference call
        # Blocking HTTP + geopandas work: keep it off the event loop.
        preds_gdf, backend = await asyncio.to_thread(inference_request, bbox)
        response.headers["X-Inference-Backend"] = backend
        
        # Save to database (assumes preds_bbox_to_database handles 3857)
        if engine:
            try:
                await asyncio.to_thread(preds_bbox_to_database, bbox.gdf, preds_gdf)
            except Exception as e:
                smtp_logger.fatal("Data not saved to database.", exc_info=True)
                logger.error(f"DB Save Error: {e}")
                
        # Return GeoJSON feature collection of predictions in EPSG:4326 for Leaflet
        preds_gdf_4326 = preds_gdf.to_crs("EPSG:4326")
        return {"features": preds_gdf_4326.__geo_interface__["features"]}

    except (BBoxTooBig, BBoxTooSmall) as e:
        raise HTTPException(status_code=422, detail=e.message)
    except Exception as e:
        logger.error(f"Inference error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/statistics")
async def get_statistics():
    try:
        pred, country = await asyncio.to_thread(read_data)
        
        # Calculate heatmap data
        pred["latitude"], pred["longitude"] = pred.geometry.y, pred.geometry.x
        heat_data = [
            {"lat": float(row.latitude), "lng": float(row.longitude)}
            for _, row in pred.iterrows()
        ]
        
        # Calculate country stats
        locations = len(pred["id_bbox"].unique())
        inter = pred.sjoin(country, how="left")
        countries_cnt = inter.groupby("name").count()
        
        country_stats = []
        for name, row in countries_cnt.iterrows():
            if name: # omit nulls
                country_stats.append({
                    "country": str(name),
                    "trees_detected": int(row["id"])
                })
            
        total_trees = sum(c["trees_detected"] for c in country_stats)
        
        return {
            "heatmap": heat_data,
            "metrics": {
                "locations_covered": int(locations),
                "total_trees_detected": total_trees
            },
            "countries": country_stats,
            "center": config["statistics_ui"]["center"],
            "zoom": config["statistics_ui"]["zoom"]
        }
    except Exception as e:
        logger.error(f"Stats error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

# We mount static directory at the root to serve index.html directly
app.mount("/", StaticFiles(directory="static", html=True), name="static")
