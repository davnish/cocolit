from dataclasses import dataclass, field
from shapely.geometry import Point
from geopandas import GeoDataFrame
from shapely.geometry import shape
import rasterio as rio
import numpy as np
import pandas as pd
import geopandas as gpd
from src.exceptions.exceptions import BBoxTooBig, BBoxTooSmall
from src.utils.PatchRaster import PatchRaster
from pydantic import BaseModel
from src.data_struct.getpath import GetPath
from shapely.geometry import box
from typing import Union


class BBoxBounds(BaseModel):
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def to_list(self) -> list:
        """Return bounds as a list."""
        return [self.xmin, self.ymin, self.xmax, self.ymax]
    
    def to_bounds_dict(self) -> dict:
        """Return bounds as a dictionary."""
        return {
            "xmin": self.xmin,
            "ymin": self.ymin,
            "xmax": self.xmax,
            "ymax": self.ymax,
        }
    @classmethod
    def from_geojson(cls, data: dict) -> "BBoxBounds":
        geometry = shape(data["geometry"])
        bounds = geometry.bounds
        return cls(
            xmin=bounds[0],
            ymin=bounds[1],
            xmax=bounds[2],
            ymax=bounds[3],
        )

@dataclass
class BBox:
    data: Union[dict, BBoxBounds]
    # values to be initialized post creation
    gdf: GeoDataFrame = field(init=False, default=None) # GeoDataFrame representation of the bbox
    area: float = field(init=False, default=0) # Area of the bbox in square meters
    bounds: int = field(init=False, default_factory=list) # Bounds of the bbox as [xmin, ymin, xmax, ymax]
    preds: GeoDataFrame = field(init=False, default=None) # Predictions as GeoDataFrame
    path: GetPath = field(init=False, default=None) # Paths for temporary storage
 
    def __post_init__(self) -> None:
        if isinstance(self.data, dict):
            self.gdf = self.geojson_to_gdf(self.data)
            self.bounds = self.gdf.to_crs(4326).bounds.to_numpy().tolist()[0]
        else:
            self.gdf = self.bounds_to_gdf(self.data)
            self.bounds = self.data.to_list()
        self.area = self.gdf.geometry.iloc[0].area
        self.path = GetPath()

    def bounds_to_gdf(self, data: BBoxBounds) -> GeoDataFrame:
        polygon = box(*data.to_list())
        gdf = gpd.GeoDataFrame({"geometry": [polygon]}, crs="EPSG:4326")
        return gdf.to_crs(3857)

    def geojson_to_gdf(self, data: dict) -> GeoDataFrame:
        """
        Convert GeoJSON to Shapefile

        Here, geographical coordinates (EPSG:4326) are converted to geometric coordinates (EPSG:3857).
        This is done to calcualte the Buffer afterward.
        """
        geometry = shape(data["geometry"])
        gdf = GeoDataFrame(geometry=[geometry], crs="EPSG:4326").to_crs(3857)
        return gdf

    def valid_bbox(self) -> bool:
        """Check if the bounding box is valid."""

        # if bbox area is more than 10 km2
        if self.area > 5e6:
            raise BBoxTooBig
        # if bbox area is less than 25 m2
        elif self.area < 625:
            raise BBoxTooSmall

    def preprocess(self) -> None:
        """
        There is only one precessing step here which is patching the raster.
        Further steps for preprocessing are handled by ultralytics
        """
        PatchRaster(
            self.path.image_path,
            output_patched_ras=self.path.patched,
            patch_size=640,
            padding=True,
        )

    def get_preds(self, res: list) -> Union[GeoDataFrame, None]:
        """
        Post Process output from the model
        """
        preds = None
        for idx, i in enumerate(res):
            if res[idx].boxes.shape[0] > 0:
                _res = res[idx].boxes.numpy()
                xywhn = _res.xywhn
                conf = np.expand_dims(_res.conf, axis=1)

                pred = np.concatenate((conf, xywhn), axis=-1)

                with rio.open(i.path) as src:
                    bounds = src.bounds
                    crs = src.crs
                    top_left_corner = (bounds.left, bounds.top)
                    bottom_right_corner = (bounds.right, bounds.bottom)

                df = pd.DataFrame(pred, columns=["conf", "x", "y", "width", "height"])

                df["x"] = (
                    df["x"] * (bottom_right_corner[0] - top_left_corner[0])
                    + top_left_corner[0]
                )
                df["y"] = top_left_corner[1] - df["y"] * (
                    top_left_corner[1] - bottom_right_corner[1]
                )
                df["geometry"] = [Point(x, y) for x, y in zip(df.x, df.y)]

                pred = gpd.GeoDataFrame(
                    df.loc[:, ["conf", "geometry"]], geometry="geometry", crs=crs
                )

                if preds is None:
                    preds = pred
                else:
                    preds = pd.concat([preds, pred], ignore_index=True)

        return preds

    def to_dict(self) -> dict:
        return {
            'xmin': self.bounds[0],
            'ymin': self.bounds[1],
            'xmax': self.bounds[2],
            'ymax': self.bounds[3],
        }