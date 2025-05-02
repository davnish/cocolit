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

@dataclass
class GetPath:
    temp_name: str = 'image'
    dir: Path = field(init=False)
    image_path: Path = field(init=False)
    txt_path: Path = field(init=False)

    def __post_init__(self):
        self.dir = Path(tempfile.mkdtemp(dir = 'data/'))
        self.image_path = self.dir / f"{self.temp_name}.tif"
        self.txt_path = self.dir / f"predict/labels/{self.temp_name}.txt"
    
    def rm(self):
        shutil.rmtree(self.dir)

@dataclass
class BBox:
    data : dict
    gdf  : GeoDataFrame = field(init = False, default=None)
    area : float = field(init = False, default=0)
    bounds : int = field(init = False, default_factory=list)
    preds : GeoDataFrame = field(init = False, default = None)
    path : GetPath = field(init = False, default = None)

    def __post_init__(self) -> None:
        self.gdf= self.get_shapefile(self.data)
        self.area = self.gdf.geometry.iloc[0].area
        self.bounds = self.gdf.to_crs(epsg=4326).bounds.to_numpy().tolist()[0]
        self.path = GetPath()
    
    def get_shapefile(self, data) -> GeoDataFrame:
      """
      Convert GeoJSON to Shapefile
      """
      geometry = shape(data['geometry'])
      gdf = GeoDataFrame(geometry=[geometry], crs="EPSG:4326").to_crs(epsg=3857)
      return gdf

    def valid_bbox(self) -> bool:
        """Check if the bounding box is valid."""

        # if bbox area is more than 5 km2
        if self.area > 5e6:
            raise InvalidBBox("Bounding box area exceeds the maximum limit of 5 km2.")
        # if bbox area is less than 0.1 km2
        elif self.area < 1e4:
            raise InvalidBBox("Bounding box area is less than the minimum limit of 0.1 km2.")    
        
    def get_preds(self, res: list) -> GeoDataFrame | None:
        if res[0].boxes.shape[0]>0:
            res = res[0].boxes.numpy()
            xywhn = res.xywhn
            conf = np.expand_dims(res.conf, axis=1)

            pred = np.concat((conf, xywhn), axis=-1)
            
            with rio.open(self.path.image_path) as src:
                bounds = src.bounds
                crs = src.crs
                top_left_corner = (bounds.left, bounds.top)
                bottom_right_corner = (bounds.right, bounds.bottom)    
            
            df = pd.DataFrame(pred, columns = ['conf', 'x', 'y', 'width', 'height'])  

            df['x'] = df['x'] * (bottom_right_corner[0] - top_left_corner[0]) + top_left_corner[0]
            df['y'] = top_left_corner[1] - df['y'] * (top_left_corner[1] - bottom_right_corner[1])

            df['centroid'] = [Point(x, y) for x, y in zip(df.x, df.y)]

            preds = gpd.GeoDataFrame(geometry = df['centroid'], crs = crs).to_crs(epsg=4326)
            return preds
        else:
            return None
            
    
if __name__ == '__main__':
    data = {"type":"Feature",
    "properties":{},
    "geometry":{
        "type":"Polygon",
        "coordinates":[[[-85.078125,38.61687],[-85.078125,41.771312],
                        [-81.430664,41.771312],[-81.430664,38.61687],
                        [-85.078125,38.61687]]]
                        }}
    
    # _bbox = BBox(data = data)
    # print(_bbox.area)
    # # _bbox.pred = 0
    # print(_bbox.bounds)


    temp = GetPath()
    temp2 = GetPath()
    print(temp.dir)
    print(temp2)

