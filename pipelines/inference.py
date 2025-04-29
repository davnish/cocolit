from ultralytics import YOLO
from src.exceptions import InvalidBBox
from src.geojson_to_shapefile import get_shapefile
from src.download import TMStoGeoTIFF
from src.txt_to_shp import txt_to_shp
from src.valid_bbox import valid_bbox
from pathlib import Path
import geopandas as gpd
import tempfile

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def inference(
        bbox: dict,
        model_path: str | None = None, 
        ) -> Path:
    """
    This is a pipeline for inference on finetunned YOLOv11 model.
    """

    # Create a temporary file to store the downloaded image
    try:

        bbox = get_shapefile(bbox)
        logging.info("Geojson to Shapefile conversion done")

        valid_bbox(bbox)
        logging.info(f"Valid bounding box : {bbox.to_crs(epsg=4326).bounds.to_numpy().tolist()[0]}")

        with tempfile.NamedTemporaryFile(delete=True, suffix = '.tif') as temp_file:
            image_path = Path(temp_file.name)
        logging.info(f"Temporary image path created: {image_path}")


        data = TMStoGeoTIFF(output=image_path, bbox=bbox.to_crs(epsg=4326).bounds.to_numpy().tolist()[0]) ###### This will change after db integration. After each prediction we will update the name of the file.
        data.download()
        logging.info(f"Image downloaded: {image_path}")

        with tempfile.TemporaryDirectory() as temp_txt_file:
            txt_dir_path = Path(temp_txt_file)
        logging.info(f"Temporary txt directory created: {txt_dir_path}")

        model = YOLO("yolo11n.pt")
        logging.info(f"Model loaded")

        model.predict(source=image_path, save=True, save_txt=True, project=txt_dir_path)
        logging.info(f"Prediction done. Text files saved to: {txt_dir_path}")

        with tempfile.TemporaryDirectory() as temp_shp_file:
            shp_dir_path = Path(temp_shp_file)
        logging.info(f"Temporary shapefile directory created: {shp_dir_path}")

        shp_path = txt_to_shp(txt_dir_path, image_path.parents, shp_dir_path)
        logging.info(f"Shapefile created at: {shp_path}")
        return shp_path
    
    except InvalidBBox as e:
        logger.error(f"Invalid bounding box: {e}")
        return None

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return None





if __name__ == "__main__":
    data = {"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[74.347916,24.287027],[74.347916,24.293129],[74.355469,24.293129],[74.355469,24.287027],[74.347916,24.287027]]]}}
    shp = inference(data)
    print(shp)
