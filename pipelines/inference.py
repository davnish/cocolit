from ultralytics import YOLO
from src.exceptions import InvalidBBox
from src.download import TMStoGeoTIFF
from src.bbox import BBox
from src.database.dal.preds import preds_bbox_to_database

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
                logger.info(f"results conversion to GeoDataFrame done")
                try:
                    logger.info("Sending data to database")
                    preds_bbox_to_database(bbox.gdf, bbox.preds)
                except Exception as e:
                    logger.error(f"ERROR: Data not saved in server. most probably server down. {e}")

                logger.info("Data Saved to Database")
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
            logger.info("Paths removed")


if __name__ == "__main__":
    data = {"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[80.020219,7.809309],[80.020219,7.810361],[80.021667,7.810361],[80.021667,7.809309],[80.020219,7.809309]]]}}
    bbox = BBox(data)
    inference = InferencePipeline("models/train15/weights/best.pt")
    bbox = inference.run(bbox)
    print(bbox.preds)
