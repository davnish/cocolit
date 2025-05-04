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
from src.PatchRaster import PatchRaster
import uuid

@dataclass
class GetPath:
    temp_name: str = 'image'
    dir: Path = field(init=False)
    image_path: Path = field(init=False)
    save_path: Path = field(init=False)
    patched : Path = field(init=False)


    def __post_init__(self):
        self.dir = Path(tempfile.mkdtemp(dir = 'data/'))
        self.image_path = self.dir / f"{self.temp_name}.tif"
        self.save_path = Path('data', 'preds.shp')
        self.patched = self.dir / "patched"

        self.patched.mkdir(parents=True, exist_ok=True)
    
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
    id   : str = field(default_factory=lambda : str(uuid.uuid4()))

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

                pred = gpd.GeoDataFrame(df, geometry='geometry', crs = crs).to_crs(epsg=4326)

                if preds is None:
                    preds = pred
                else:
                    preds = df = pd.concat([preds, pred], ignore_index = True)
                    
        return preds
    
    def save(self) -> None:
        if self.preds is not None:
            self.preds['id'] = self.id
            column_order = ['id', 'conf', 'x', 'y', 'width', 'height', 'geometry']
            self.preds = self.preds[column_order]

            if self.path.save_path.exists():
                existing = gpd.read_file(self.path.save_path)
                combined = pd.concat([existing, self.preds], ignore_index=True)
            else:
                combined = self.preds

            combined.to_file(self.path.save_path, driver= 'ESRI Shapefile', index=False)
                

    def preprocess(self) -> None:
        PatchRaster(self.path.image_path, output_patched_ras=self.path.patched, patch_size=640, padding=True)
        
                 
    
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

