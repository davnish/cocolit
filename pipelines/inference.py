from ultralytics import YOLO
from src.exceptions import InvalidBBox
from src.geojson_to_shapefile import get_shapefile
from src.download import TMStoGeoTIFF
from src.txt_to_shp import txt_to_shp
from src.valid_bbox import valid_bbox
from pathlib import Path
import geopandas as gpd
import tempfile
import shutil

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def inference(
        bbox: dict,
        model_path: str | None = None, 
        temp_dir: str | None = None
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

        # with tempfile.TemporaryDirectory(dir = '.') as temp_dir:
        if temp_dir is None:
            temp_dir = Path(tempfile.mkdtemp(dir = '.'))
        temp_name = 'image'

        logging.info(f"Temporary directory created: {temp_dir}")

        image_path = temp_dir / (temp_name + '.tif')
        logging.info(f"Temporary image path created: {image_path}")

        data = TMStoGeoTIFF(output=image_path, bbox=bbox.to_crs(epsg=4326).bounds.to_numpy().tolist()[0]) ###### This will change after db integration. After each prediction we will update the name of the file.
        data.download()
        logging.info(f"Image downloaded: {image_path}")

        model = YOLO(model_path)
        logging.info(f"Model loaded")

        model.predict(source=image_path, save_txt=True, project=image_path.parent)
        logging.info(f"Prediction done. Text files saved to: {temp_dir}/predict/labels/{temp_name + '.txt'}")

        shp_path = txt_to_shp(
            txt_dir=temp_dir / f"predict/labels/{(temp_name + '.txt')}", 
            img_dir=temp_dir, 
            shp_dir=temp_dir
            )
        
        logging.info(f"Shapefile created at: {shp_path}")
        return shp_path
    
    except InvalidBBox as e:
        logger.error(f"Invalid bounding box: {e}")
        return None

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
        return None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logging.info(f"Temporary directory removed: {temp_dir}")


if __name__ == "__main__":
    data = {"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[80.020219,7.809309],[80.020219,7.810361],[80.021667,7.810361],[80.021667,7.809309],[80.020219,7.809309]]]}}
    shp = inference(data, "models/train15/weights/best.pt")
    print(shp)
