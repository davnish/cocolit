from ultralytics import YOLO
from src.exceptions import InvalidBBox
from src.download import TMStoGeoTIFF
from src.bbox import BBox
import logging
from rich.logging import RichHandler


# logging.config.fileConfig('configs/logging.config')
# logger = logging.getLogger('inference')
# logger.handlers[0] = RichHandler(markup=True)

from src.logger_config import setup_logger

logger = setup_logger('inference', 'inference.log')

# converting to class

class InferencePipeline:
    def __init__(
            self, 
            model_path: str,
            )->None:
    
        self.model = YOLO(model_path, task='detect')

    def run(self, bbox : BBox) -> BBox | None:
        try:

            bbox.valid_bbox()
            logger.info("Processed and validated bbox")

            data = TMStoGeoTIFF(output=bbox.path.image_path, bbox=bbox.bounds) ###### This will change after db integration. After each prediction we will update the name of the file.
            data.download()
            logger.info("Downloaded the images")

            bbox.preprocess()
            logger.info("Patching the raster")

            res = self.model.predict(source=bbox.path.patched)
            logger.info(f"Inference done")
            
            bbox.preds = bbox.get_preds(res)

            if bbox.preds is not None:
                logger.info(f"results to GeoDataFrame Done, Total preds of trees {len(bbox.preds)}.")
            
            else:
                logger.info(f"No Predictions found")

            return bbox

        except InvalidBBox as e:
            logger.error(f"Invalid bounding box: {e}")
            return None

        except Exception as e:
            logger.error(f"An error occurred: {e}", exc_info=True)
            return None
        
        finally:
            bbox.path.rm()
            bbox.save()
            logger.info("Paths removed")


if __name__ == "__main__":
    data = {"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[80.020219,7.809309],[80.020219,7.810361],[80.021667,7.810361],[80.021667,7.809309],[80.020219,7.809309]]]}}
    bbox = BBox(data)
    inference = InferencePipeline("models/train15/weights/best.pt")
    bbox = inference.run(bbox)
    print(bbox.preds)
