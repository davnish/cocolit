from src.download import TMStoGeoTIFF
from src.PatchRaster import PatchRaster
from src.PatchVector import PatchVector
from src.vec_to_txt import vectors_to_labels
from src.train_test_split import train_test_split
from src.copy_data import copy_data
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)

def PrepareDataset(
        bbox: list, 
        raster_path: str, 
        raster_patch_path: str,
        vector_path: str,
        vector_patch_path: str,
        txt_patch_path: str,
        dataset_path: str
        ) -> None:

    try:

        data = TMStoGeoTIFF(output=raster_path, bbox=bbox)
        data.download()
        logging.info(f"Data downloaded and saved to {raster_path}")

        PatchRaster(raster_path, output_patched_ras=raster_patch_path, patch_size=640, padding=True)
        logging.info(f"Raster patched and saved to {raster_patch_path}")

        PatchVector(raster_patch_path, vector_path, output_patched_vector=vector_patch_path)
        logging.info(f"Vector patched and saved to {vector_patch_path}")

        vectors_to_labels(raster_path, vector_path, txt_patch_path)
        logging.info(f"Vector labels saved to {txt_patch_path}")
            
        trainx, trainy, testx, testy = train_test_split(raster_patch_path, txt_patch_path, train_size=0.8)
        testx, testy, valx, valy = train_test_split(raster_patch_path, txt_patch_path, train_size=0.5)
        logging.info(f"Train and test data split. Train size: {len(trainx)}, Test size: {len(testx)}, Val size: {len(valx)}")

        dataset = {
            "trainx": trainx,
            "trainy": trainy,
            "testx": testx,
            "testy": testy,
            "valx": valx,
            "valy": valy
        }
        copy_data(dataset, dataset_path)
        logging.info("Data copied to respective directories.")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise e








    
if __name__ == "__main__":
    pass