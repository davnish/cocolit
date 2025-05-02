from ultralytics import YOLO
from src.exceptions import InvalidBBox
# from src.geojson_to_shapefile import get_shapefile
from src.download import TMStoGeoTIFF
from src.txt_to_shp import txt_to_shp
# from src.valid_bbox import valid_bbox
# from src.datacls import get_path
from src.bbox import BBox
from pathlib import Path
import geopandas as gpd
from geopandas import GeoDataFrame
import tempfile
import shutil
import time
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# converting to class

class InferencePipeline:
    def __init__(
            self, 
            model_path: str,
            )->None:
    
        self.model = YOLO(model_path, task='detect')

    def run(self, bbox : BBox) -> BBox:
        try:

            bbox.valid_bbox()
            logger.info("Processed and validated bbox")

            data = TMStoGeoTIFF(output=bbox.path.image_path, bbox=bbox.bounds) ###### This will change after db integration. After each prediction we will update the name of the file.
            data.download()
            logger.info("Downloaded the images")

            res = self.model.predict(source=bbox.path.image_path)
            logger.info(f"Inference done")
            
            # breakpoint()
            bbox.preds = bbox.get_preds(res)

            if bbox.preds is not None:
                logger.info(f"results to GeoDataFrame Done, Total preds of trees {len(bbox.preds)}.")
                return bbox
            
            else:
                logger.info(f"No Predictions found")
                return None

        except InvalidBBox as e:
            logger.error(f"Invalid bounding box: {e}")
            return None

        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
            return None
        
        finally:
            bbox.path.rm()
            logger.info("Paths removed")


if __name__ == "__main__":
    data = {"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[80.020219,7.809309],[80.020219,7.810361],[80.021667,7.810361],[80.021667,7.809309],[80.020219,7.809309]]]}}
    bbox = BBox(data)
    inference = InferencePipeline("models/train15/weights/best.pt")
    bbox = inference.run(bbox)
    print(bbox.preds)
