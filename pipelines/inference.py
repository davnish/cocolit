from ultralytics import YOLO
from src.utils.download import TMStoGeoTIFF
from src.data_struct.bbox import BBox
from configs.logger import setup_logger
from typing import Union

logger = setup_logger("inference", "inference.log")


class InferencePipeline:
    def __init__(
        self,
        model_path: str,
    ) -> None:
        self.model = YOLO(model_path, task="detect")

    def run(self, bbox: BBox) -> Union[BBox, None]:
        try:
            bbox.valid_bbox()
            logger.info("Processed and validated bbox")

            TMStoGeoTIFF(output=bbox.path.image_path, bbox=bbox.bounds)
            logger.info("Downloaded the images")

            bbox.preprocess()
            logger.info("Patching the raster")

            res = self.model.predict(source=bbox.path.patched)
            logger.info("Inference done")

            bbox.preds = bbox.get_preds(res)

            return bbox

        except:
            raise

        finally:
            bbox.path.rm()
            logger.info("Paths removed")
