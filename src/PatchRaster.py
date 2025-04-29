from rasvec import patchify_raster
from pathlib import Path
# import logging

def PatchRaster(ras_path: str, output_patched_ras: str, patch_size: int = 640, padding: bool = True) -> None:
    """
    Patch a raster file into smaller patches.

    Args:
        ras_path (Path): Path to the input raster file.
        output_patched_ras (Path): Path to save the patched raster files.
    """
    # Call the function to patch the raster

    ras_path = Path(ras_path)
    output_patched_ras = Path(output_patched_ras)

    patchify_raster(ras_path, output_path=output_patched_ras, patch_size=patch_size, padding=padding)