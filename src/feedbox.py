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

logger = setup_logger('feedbox', 'feedbox.log')

@dataclass
class FeedBox:
    id_preds : str 
    pos : str
    feedback_path : Path = Path("data/feedback.shp")
    image_path : Path = field(init=False, default=None)
    # feedback : bool = field(init=False, default=None)
    bounds: bool = field(init=False, default=None)
    
    dir: Path = Path('data/feedback')

    def __post_init__(self):
        gdf = gpd.read_file(self.feedback_path)
        self.image_path = self.dir / (self.id_preds + '.tiff')
        self.gdf = gdf.loc[gdf['id_preds'] == self.id_preds, :]
        self.bounds = self.get_bounds()
    
    def update_value(self, column):
        gdf = gpd.read_file(self.feedback_path)
        gdf.loc[gdf['id_preds'] == self.id_preds, column] += 1
        gdf.to_file(self.feedback_path, driver='Esri Shapefile', index=False)
        
    def buffer(self):
        _buffer  = self.gdf.to_crs(epsg=3857).buffer(15, cap_style='square')
        _buffer = _buffer.to_crs(4326)
        return _buffer
    
    def get_bounds(self):
        buffer = self.buffer()
        return buffer.bounds.to_numpy().tolist()[0]

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
    feedback_path : Path = Path('data/feedback.shp')
    id_preds: list[str] = field(default_factory=list)

    def __post_init__(self):
        gdf = gpd.read_file(self.feedback_path)
        self.id_preds.extend(gdf.loc[:, 'id_preds'].to_numpy().tolist())

    def enqueue(self, id):
        return self.id_preds.append(id)
    
    def dequeue(self):
        return self.id_preds.pop(0)
    
    def dequeue_enqueue(self):
        id = self.dequeue()
        self.enqueue(id)
        return id

    
    




             


