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
from datetime import datetime
import uuid

from src.logger_config import setup_logger

logger = setup_logger('bbox', 'bbox.log')

@dataclass
class GetPath:
    temp_name: str = 'image'
    dir: Path = field(init=False)
    image_path: Path = field(init=False)
    patched : Path = field(init=False)
    preds_path: Path = field(init=False)
    bbox_path : Path = field(init=False)
    feedback_path : Path = field(init=False)


    def __post_init__(self):
        self.dir = Path(tempfile.mkdtemp(dir = 'data/'))
        self.image_path = self.dir / f"{self.temp_name}.tif"
        self.patched = self.dir / "patched"
        self.patched.mkdir(parents=True, exist_ok=True)

        self.preds_path = Path('data', 'preds.shp')
        self.bbox_path = Path('data', 'bbox.shp')
        self.feedback_path = Path('data', 'feedback.shp')

    
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
    low_conf : int = field(init=False, default=None)
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
    
    def preprocess(self) -> None:
        PatchRaster(self.path.image_path, output_patched_ras=self.path.patched, patch_size=640, padding=True)
        
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
                    preds = pd.concat([preds, pred], ignore_index = True)

                logger.debug(f'preds of {idx} tile {preds.shape}')
                    
        return preds

    def get_preds_feedback_gdf(self) -> tuple[GeoDataFrame, GeoDataFrame]:
        self.preds['id'] = self.id
        self.preds['id_preds'] = [str(uuid.uuid4()) for i in range(len(self.preds))]
        
        feedback = self.preds[self.preds['conf']<0.5].copy()
        feedback['yes'] = 0
        feedback['no'] = 0

        self.low_conf = len(feedback)

        preds = self.preds.drop(feedback.index)
        
        column_order_preds = ['id', 'id_preds', 'conf', 'x', 'y', 'width', 'height', 'geometry']
        column_order_feedback = ['id', 'id_preds', 'conf', 'x', 'y', 'width', 'height', 'yes', 'no', 'geometry']
        
        preds = preds[column_order_preds]
        feedback = feedback[column_order_feedback]

        if self.path.preds_path.exists():
            existing_preds = gpd.read_file(self.path.preds_path)
            combined_preds = pd.concat([existing_preds, preds], ignore_index=True)

            existing_feedback = gpd.read_file(self.path.feedback_path)
            combined_feedback = pd.concat([existing_feedback, preds], ignore_index=True)
        else:
            combined_preds = preds
            combined_feedback = feedback

        return combined_preds, combined_feedback

    def save(self):
        if self.preds is not None:
            try:
                preds, feedback = self.get_preds_feedback_gdf()
                bbox = self.get_bbox_gdf(len(feedback))

                preds.to_file(self.path.preds_path, driver= 'ESRI Shapefile', index=False)
                feedback.to_file(self.path.feedback_path, driver= 'ESRI Shapefile', index=False)
                bbox.to_file(self.path.bbox_path, driver= 'ESRI Shapefile', index=False)
                
                logger.info(f'Saved bbox, preds and feedback gdf')

            except Exception as e:
                logger.error('Error Not able to save the gdf', exc_info=True) # change this to log
        else:
            logger.info('No preds saved.')
    
    def get_bbox_gdf(self, low_conf: int) -> GeoDataFrame:
        self.gdf['datetime'] = datetime.now()
        self.gdf['low_conf'] = low_conf
        self.gdf['id'] = self.id
        gdf = self.gdf[['id', 'datetime', 'low_conf', 'geometry']]
        if self.path.bbox_path.exists():
            existing = gpd.read_file(self.path.bbox_path)
            combined = pd.concat([existing, gdf], ignore_index=True)
        else:
            combined = gdf
        return combined
    
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

