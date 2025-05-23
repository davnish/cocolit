from ultralytics import YOLO
from src.utils.download import TMStoGeoTIFF
from src.data_struct.bbox import BBox
from src.dal.preds import preds_bbox_to_database
from configs.logger import setup_logger
from typing import Union

logger = setup_logger("inference", "inference.log")


class InferencePipeline:
    def __init__(
        self,
        model_path: str,
    ) -> None:
        self.model = YOLO(model_path, task="detect")

    def run(self, bbox: BBox, conn: Union[bool, None] = False) -> Union[BBox, None]:
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

            if bbox.preds is not None:
                logger.info("results conversion to GeoDataFrame done")
                if conn:
                    try:
                        preds_bbox_to_database(bbox.gdf, bbox.preds)
                        logger.info("Data Saved to database")
                    except Exception as e:
                        logger.error(
                            f"ERROR: Data not saved in server. most probably server down. {e}"
                        )

                logger.info("Data Saved to Database")
            else:
                logger.info("No Predictions found")

            return bbox

        except:
            raise

        finally:
            bbox.path.rm()
            logger.info("Paths removed")


if __name__ == "__main__":
    from pathlib import Path

    data = {
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [80.020219, 7.809309],
                    [80.020219, 7.810361],
                    [80.021667, 7.810361],
                    [80.021667, 7.809309],
                    [80.020219, 7.809309],
                ]
            ],
        },
    }
    bbox = BBox(data)
    inference = InferencePipeline(Path("models/best.onnx"))
    bbox = inference.run(bbox)
    print(bbox.preds)
