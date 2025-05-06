from rasvec import tms_to_geotiff
from pathlib import Path


class TMStoGeoTIFF:
    """
    Class to handle downloading TMS data and converting it to GeoTIFF format.
    """

    def __init__(
            self, 
            output : Path, 
            bbox : list, 
            source : str = 'satellite', 
            zoom : int = 19,
            overwrite : bool = True,
            quiet : bool = True,
            ) -> None:
        
        self.output_file = output
        self.bbox = bbox
        self.source = source
        self.overwrite = overwrite
        self.zoom = zoom
        self.quiet = quiet
        
    def download(self) -> None:
        """
        Download TMS data and convert to GeoTIFF format.
        """
        tms_to_geotiff(
            output=self.output_file, 
            bbox=self.bbox, 
            source=self.source, 
            zoom=self.zoom, 
            overwrite=self.overwrite, 
            quiet=self.quiet
            )
        
        
if __name__ == "__main__":
    # Example usage
    bbox = [74.347916, 24.287027, 74.355469, 24.293128999999997]
    output = Path("output.tif")
    downloader = TMStoGeoTIFF(output=output, bbox=bbox)
    downloader.download()





