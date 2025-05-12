from dataclasses import dataclass, field
import tempfile
import shutil
from pathlib import Path
from shapely.geometry import Point
from geopandas import GeoDataFrame
from shapely.geometry import shape
import rasterio as rio
from .exceptions import InvalidBBox
import numpy as np
import pandas as pd
import geopandas as gpd
from .PatchRaster import PatchRaster
from pydantic import BaseModel
from .logger_config import setup_logger
from shapely.geometry import box

logger = setup_logger('bbox', 'bbox.log')

@dataclass
class GetPath:
    temp_name: str = 'image'
    dir: Path = field(init=False)
    image_path: Path = field(init=False)
    patched : Path = field(init=False)

    def __post_init__(self):
        dir = Path('data').mkdir(parent=True, exist_ok=True)
        self.dir = Path(tempfile.mkdtemp(dir = dir))
        self.image_path = self.dir / f"{self.temp_name}.tif"
        self.patched = self.dir / "patched"
        self.patched.mkdir(parents=True, exist_ok=True)

    def rm(self):
        shutil.rmtree(self.dir)

class BBoxBounds(BaseModel):
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    
    def to_list(self):
        """Return bounds as a list."""
        return [self.xmin, self.ymin, self.xmax, self.ymax]

@dataclass
class BBox:
    data : dict | BBoxBounds
    gdf  : GeoDataFrame = field(init = False, default=None)
    area : float = field(init = False, default=0)
    bounds : int = field(init = False, default_factory=list)
    preds : GeoDataFrame = field(init=False, default=None)
    path : GetPath = field(init = False, default = None)

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
        gdf = gpd.GeoDataFrame({'geometry': [polygon]}, crs="EPSG:4326")
        return gdf.to_crs(3857)
    
    def geojson_to_gdf(self, data) -> GeoDataFrame:
      """
      Convert GeoJSON to Shapefile

      Here, geographical coordinates (EPSG:4326) are converted to geometric coordinates (EPSG:3857).
      This is done to calcualte the Buffer afterward.
      """
      geometry = shape(data['geometry'])
      gdf = GeoDataFrame(geometry=[geometry], crs="EPSG:4326").to_crs(3857)
      return gdf

    def valid_bbox(self) -> bool:
        """Check if the bounding box is valid."""

        # if bbox area is more than 5 km2
        if self.area > 5e6:
            raise InvalidBBox("Bounding box area exceeds the maximum limit of 5 km2.")
        # if bbox area is less than 0.1 km2
        elif self.area < 1e4:
            raise InvalidBBox("Bounding box area is less than the minimum limit of 0.1 km2.")    
    
    def preprocess(self) -> None:
        """
        There is only one precessing step here which is patching the raster.
        Further steps for preprocessing are handled by ultralytics
        """
        PatchRaster(self.path.image_path, output_patched_ras=self.path.patched, patch_size=640, padding=True)
        
    def get_preds(self, res: list) -> GeoDataFrame | None:
        """
        Post Process output from the model
        """
        preds = None
        for idx, i in enumerate(res): 
            if res[idx].boxes.shape[0]>0:
                _res = res[idx].boxes.numpy()
                xywhn = _res.xywhn
                conf = np.expand_dims(_res.conf, axis=1)

                pred = np.concat((conf, xywhn), axis=-1)
                
                with rio.open(i.path) as src:
                    bounds = src.bounds
                    crs = src.crs
                    top_left_corner = (bounds.left, bounds.top)
                    bottom_right_corner = (bounds.right, bounds.bottom)    
                
                df = pd.DataFrame(pred, columns = ['conf', 'x', 'y', 'width', 'height'])  

                df['x'] = df['x'] * (bottom_right_corner[0] - top_left_corner[0]) + top_left_corner[0]
                df['y'] = top_left_corner[1] - df['y'] * (top_left_corner[1] - bottom_right_corner[1])
                df['geometry'] = [Point(x, y) for x, y in zip(df.x, df.y)]

                pred = gpd.GeoDataFrame(df.loc[:, ['conf', 'geometry']], geometry='geometry', crs = crs)

                if preds is None:
                    preds = pred
                else:
                    preds = pd.concat([preds, pred], ignore_index = True)

                logger.debug(f'preds of {idx} tile {preds.shape}')
                    
        return preds
    
if __name__ == '__main__':
    data = {"type":"Feature",
    "properties":{},
    "geometry":{
        "type":"Polygon",
        "coordinates":[[[-85.078125,38.61687],[-85.078125,41.771312],
                        [-81.430664,41.771312],[-81.430664,38.61687],
                        [-85.078125,38.61687]]]
                        }}
    


