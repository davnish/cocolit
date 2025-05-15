from dataclasses import dataclass, field
from pathlib import Path
import streamlit as st
import numpy as np
import geopandas as gpd
from src.download import TMStoGeoTIFF

from .database.dal.feedback import FeedbackDAO
from PIL import Image, ImageDraw


@dataclass
class FeedBox:
    pos : str
    id_bounds : list = field(default_factory=list)

    def __post_init__(self):
        self.id = self.id_bounds[0]
        self.bounds = self.id_bounds[1]
        self.dir: Path = Path('data/feedback')
        self.dir.mkdir(parents=True, exist_ok=True)
        self.image_path = self.dir / f"{self.id}.tiff"

    def update_value(self, col):
        FeedbackDAO().update_by_id(self.id, col)

    def download(self):
        return TMStoGeoTIFF(self.image_path, bbox=self.bounds, return_image=True)

    def make_feedbox(self):
        """This makes the feedback boxes, shown the main.
        """
        if not self.image_path.exists():
            img = self.download()
        else:
            img = Image.open(self.image_path).convert('RGB')

        img_np = np.asarray(img)

        width, height = img_np.shape[:2]
        centroid = (width // 2, height // 2)

        draw = ImageDraw.Draw(img)
        draw.circle(centroid,radius=16, fill=None, outline=(255, 255, 0), width=1)

        st.image(img, use_container_width=True)

        yes_key = f"{self.pos}_yes"
        no_key = f"{self.pos}_no"
        bcol = st.columns(2)

        with bcol[0]:
            if st.button('Yes', key=yes_key, use_container_width=True, type='primary'):
                self.update_value('yes')
        
        with bcol[1]:
            if st.button('No', key=no_key, use_container_width=True):
                self.update_value('no') 

@dataclass
class Queue:
    id_bounds: list = field(default_factory=list)

    def __post_init__(self):
        id_geometry = FeedbackDAO().get_all_id_geometry()
        self.id_bounds.extend(self.get_id_bufferbounds(id_geometry))


    def get_id_bufferbounds(self, res):
        """This gives a structure to add the queue. e.g [id, [geometry]]"""
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
    
    def __len__(self):
        return len(self.id_bounds)
    
    def dequeue_enqueue(self):
        id_bound = self.dequeue()
        if id_bound is not None:
            self.enqueue(id_bound)
        return id_bound
    

if __name__ == "__main__":
    from time import perf_counter

    st = perf_counter()
    q = Queue()
    # print(q.dequeue_enqueue()[1])
    ed = perf_counter()
    print(ed-st)