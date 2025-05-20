from pathlib import Path
import rasterio as rio
import geopandas as gpd
import pandas as pd


def vectors_to_labels(ras_path, vec_path, output_path):
    """Convert the shapefile to text with adding attributes of the bbox.
    All the attributes of the bbox are calculated with respect to raster's top left corner.
    The bbox is the bounding box of the vector file.
    the attributes are:
    - distx: distance in the x direction of the bbox from the
    - disty: distance in the y direction of the bbox from the
    - width: width of the bbox.
    - height: height of the bbox.

    Args:
        ras_path (str): path to the raster file.
        vec_path (str): path to the vector file.
        output_path (str): path of the directory of the output txt file.
    """

    ras_path = Path(ras_path)
    vec_path = Path(vec_path)
    output_path = Path(output_path)
    with rio.open(ras_path) as src:
        ras_bounds = src.bounds
        top_left_corner = (ras_bounds.left, ras_bounds.top)
        botton_right_corner = (ras_bounds.right, ras_bounds.bottom)

    vector = gpd.read_file(vec_path).to_crs("EPSG:3857")
    distx = []
    disty = []
    width = []
    height = []
    for feature in vector["geometry"]:
        try:
            if feature is not None:
                distx.append(
                    abs(feature.x - top_left_corner[0])
                    / abs(top_left_corner[0] - botton_right_corner[0])
                )
                disty.append(
                    abs(feature.y - top_left_corner[1])
                    / abs(top_left_corner[1] - botton_right_corner[1])
                )
                width.append(5 / abs(botton_right_corner[0] - top_left_corner[0]))
                height.append(5 / abs(botton_right_corner[1] - top_left_corner[1]))

        except Exception as e:
            print(e)
            continue

    df = pd.DataFrame(
        {"class": 0, "distx": distx, "disty": disty, "width": width, "height": height}
    )
    df.to_csv(output_path / (ras_path.stem + ".txt"), index=False, sep=" ", header=None)
