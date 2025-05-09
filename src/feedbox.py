from dataclasses import dataclass, field
from pathlib import Path
import streamlit as st
import numpy as np
import cv2
# import logging
import geopandas as gpd
from .logger_config import setup_logger
from src.download import TMStoGeoTIFF
from typing import List, Any

from sqlmodel import Session
from .database.connection import engine
from .database.model import Feedback
from .database.dao.feedback_repository import FeedbackDAO


logger = setup_logger('feedbox', 'feedbox.log')

@dataclass
class FeedBox:
    pos : str
    id_bounds : list = field(default_factory=list)

    def __post_init__(self):
        self.id = self.id_bounds[0]
        self.bounds = self.id_bounds[1]
        self.dir: Path = Path('data/feedback')
        self.image_path = self.dir / f"{self.id}.tiff"

    def update_value(self, col):
        FeedbackDAO().update_by_id(self.id, col)
        

    def download(self):
        ras = TMStoGeoTIFF(self.image_path, bbox=self.bounds)
        ras.download()

    def make_feedbox(self):
        try: 
            if not self.image_path.exists():
                self.download()
                logger.info('Image Downloaded')
            
            img = cv2.imread(self.image_path, cv2.IMREAD_COLOR_RGB)
            logger.info('Image Read')

            img = np.asarray(img)

            width, height = img.shape[:2]
            centroid = (width//2, height//2)
            img = cv2.circle(img, centroid, 16, (255,255,0), 1) 

            st.image(img, use_container_width=True)

            yes_key = f"{self.pos}_yes"
            no_key = f"{self.pos}_no"
            bcol = st.columns(2)

            with bcol[0]:
                if st.button('Yes', key=yes_key, use_container_width=True, type='primary'):
                    self.update_value('yes')
                    logger.info(f'Yes pressed for {self.pos}')

            
            with bcol[1]:
                if st.button('No', key=no_key, use_container_width=True):
                    self.update_value('no') 
                    logger.info(f'No Pressed for {self.pos}')


        except Exception as e:
            logger.exception(f'ERROR: {e}')

@dataclass
class Queue:
    id_bounds: list = field(default_factory=list)

    def __post_init__(self):
        id_geometry = FeedbackDAO().get_id_geometry()
        self.id_bounds.extend(self.get_id_bufferbounds(id_geometry))

    def get_id_bufferbounds(self, res):
        gdf = gpd.GeoDataFrame(res, columns = ['id', 'geometry'])
        gdf['geometry'] = gpd.GeoSeries.from_wkt(gdf['geometry'], crs = 3857)
        bounds = gdf.set_geometry('geometry').buffer(15).to_crs(4326).bounds.to_numpy().tolist()
        id_geometry = gdf['id'].to_numpy().tolist()
        id_bounds = [[_id, bound] for _id, bound in zip(id_geometry, bounds)]
        return id_bounds
    
    def enqueue(self, id_bound):
        self.id_bounds.append(id_bound)
    
    def dequeue(self):
        if self.id_bounds:
            return self.id_bounds.pop(0)
        return None
    
    def dequeue_enqueue(self):
        id_bound = self.dequeue()
        if id_bound is not None:
            self.enqueue(id_bound)
        return id_bound
    

if __name__ == "__main__":
    import time
    st = time.time()
    q = Queue()
    print(q.dequeue_enqueue()[1])
    ed = time.time()
    print(ed-st)