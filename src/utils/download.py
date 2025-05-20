import PIL.Image
from rasvec import tms_to_geotiff
from pathlib import Path
import PIL


def TMStoGeoTIFF(
    output: Path,
    bbox: list,
    source: str = "satellite",
    zoom: int = 19,
    overwrite: bool = True,
    quiet: bool = True,
    **kwargs: dict,
) -> PIL.Image.Image | None:
    return tms_to_geotiff(
        output=output.as_posix(),
        bbox=bbox,
        source=source,
        overwrite=overwrite,
        zoom=zoom,
        quiet=quiet,
        **kwargs,
    )


if __name__ == "__main__":
    # Example usage
    bbox = [74.347916, 24.287027, 74.355469, 24.293128999999997]
    output = Path("output.tif")
    downloader = TMStoGeoTIFF(output=output, bbox=bbox)
