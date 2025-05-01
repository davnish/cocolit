from ultralytics import YOLO
from src.exceptions import InvalidBBox
from src.geojson_to_shapefile import get_shapefile
from src.download import TMStoGeoTIFF
from src.txt_to_shp import txt_to_shp
from src.valid_bbox import valid_bbox
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


    def preprocess(self, data) -> list:
        data = get_shapefile(data) # Thinking to shrink large bounding boxes
        valid_bbox(data)

        # Getting the bounds
        data = data.to_crs(epsg=4326).bounds.to_numpy().tolist()[0]
        return data

    def get_paths(self) -> tuple[str, str, str]:
        temp_name = 'image'
        dir = Path(tempfile.mkdtemp(dir = '.'))
        image_path = dir / (temp_name + '.tif')
        txt_path = dir / f"predict/labels/{(temp_name + '.txt')}"

        return dir, image_path, txt_path
    
    def rm_paths(self, dir : str) -> None:
        shutil.rmtree(dir)
    
    def run(self, data : dict) -> GeoDataFrame:
        try:
            bbox = self.preprocess(data)
            logger.info("Processed and validated bbox")

            dir, image_path, txt_path = self.get_paths()

            data = TMStoGeoTIFF(output=image_path, bbox=bbox) ###### This will change after db integration. After each prediction we will update the name of the file.
            data.download()
            logger.info("Downloaded the images")


            res = self.model.predict(source=image_path, save_txt=True, project=dir)
            logger.info(f"Inference done, preds saved at {txt_path}")

            if res[0].boxes.shape[0]>0:
                preds = txt_to_shp(
                            txt_dir=txt_path, 
                            img_dir=dir, 
                            shp_dir=dir
                            ).to_crs(epsg = 4326)
            else:
                return None
            logger.info(f"txt to shp done, Total preds of trees {len(preds)}.")
            return preds


        except InvalidBBox as e:
            logger.error(f"Invalid bounding box: {e}")
            return None

        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
            return None
        
        finally:
            self.rm_paths(dir)
            logger.info("Paths removed")


if __name__ == "__main__":
    data = {"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[80.020219,7.809309],[80.020219,7.810361],[80.021667,7.810361],[80.021667,7.809309],[80.020219,7.809309]]]}}
    
    # gdf = inference(data, "models/train15/weights/best.pt" )
    # print(gdf)

    inference = InferencePipeline("models/train15/weights/best.pt")
    gdf = inference.run(data)
    print(gdf)
