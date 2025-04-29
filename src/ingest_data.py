import geopandas as gpd
from pathlib import Path



def read_shapefile(filepath: Path) -> gpd.GeoDataFrame:
    """
    Reads a shapefile and returns a GeoDataFrame.

    Args:
        filepath (str): Path to the shapefile.

    Returns:
        gpd.GeoDataFrame: GeoDataFrame containing the shapefile data.
    """
    return gpd.read_file(filepath)