from rasvec import clip_vector_by_raster
from pathlib import Path


def PatchVector(ras_path: str, vector_path: str, output_patched_vector: str) -> None:
    """
    Patch a vector file by clipping it with a raster file.

    Args:
        ras_path (str): Path to the patched raster files.
        vector_path (str): Path to the input vector file.
        output_patched_vector (str): Path to save the patched vector files.
    """

    for i in Path(ras_path).glob("*.tif"):
        filepath = i.parents[1] / "patched_vec" / (i.stem + ".shp")
        shp_clipped = clip_vector_by_raster(i, vector_path, filepath)
        clip_vector_by_raster(vector_path, ras_path, output_patched_vector)
