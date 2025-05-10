import folium
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium
from src.bbox import BBox
from rich.logging import RichHandler
from src.logger_config import setup_logger
from enum import Enum
from pipelines.inference import InferencePipeline
from typing import List

logger = setup_logger('map_ui', 'map_ui.log')
logger.handlers[2] = RichHandler(markup=True)

class Map(Enum):
    location : List[float] = [7.551830,80.020504]
    zoom_start: int = 15
    layergroup_name : str = 'CocoLit'
    height : int = 400

@st.cache_resource
def load_inference(model_path):
    inference = InferencePipeline(model_path)
    return inference



def get_map():
    m = folium.Map(
        location=Map.location.value, 
        zoom_start=Map.zoom_start.value, 
        tiles = None,
        height=Map.height.value
        )

    tile = folium.TileLayer(
                tiles = 'http://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}',
                attr = 'Google Satellite',
                name = 'Satellite',
                overlay = False,
                control = True)

    tile.add_to(m)

    Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": False,
            "poly": False,
            "circle": False,
            "polygon": False,
            "marker": False,
            "circlemarker": False,
            "rectangle": True,
            "edit": False,
        },
    ).add_to(m)

    layer_control = folium.LayerControl()

    return m, layer_control

def init_boxes(all_drawings):
    """
    - we are generating the "bboxes" in st.session_state
    which will collect all the bbox from the folium map
    - the condition `len(all_drawings)==0` is used to
    checks if the user deletes the geometry then output['all_drawings'] will be zero,
    so to reset the st.session_state['bboxes'] list too.
    """
    if all_drawings is None or len(all_drawings)==0:
        if 'bboxes' not in st.session_state: 
            st.session_state['bboxes'] = []

        elif len(st.session_state['bboxes'])>0:
            st.session_state['bboxes'] = []
            logger.info("Init Boxes : Rerun")
            st.rerun()

def add_predictions():
    """
    If the predictions in `st.session_state['boxes']` not None the it will
    add all prediction to a feature group `pt`
    """
    pt = folium.FeatureGroup(name=Map.layergroup_name.value)
    
    if 'bboxes' in st.session_state and st.session_state['bboxes']:
        try:
            for bbox in st.session_state['bboxes']:
                if bbox.preds is not None:
                    trees = folium.GeoJson(
                        bbox.preds,
                        name='CocoTrees',
                        marker=folium.Circle(
                            radius=4, 
                            fill_color="orange", 
                            fill_opacity=0.1, 
                            color="orange", 
                            weight=1
                        ),
                        highlight_function=lambda x: {"fillOpacity": 0.8},
                    )
                    pt.add_child(trees) 

        except Exception as e:
            logger.error(f"Error adding predictions: {e}")
            st.error("Failed to add predictions. Please refresh the page.")
    return pt

def get_inference(all_drawings: dict, inference : InferencePipeline):
    if all_drawings is not None and len(all_drawings)>0:

        if len(st.session_state['bboxes'])>0 and all_drawings[-1] == st.session_state['bboxes'][-1].data:
            pass
        else:
            
            bbox = inference.run(BBox(all_drawings[-1]))
            if bbox is not None:
                st.session_state['bboxes'].append(bbox)
                logger.info("Get Inference : Rerun")
                st.rerun()
            else:
                st.error("ERROR: Please refresh the app or delete the drawings.")

def get_output(m, pt, layer_control):
    output = st_folium(m, 
            feature_group_to_add=pt, 
            use_container_width=True,
            layer_control=layer_control,
            returned_objects=['all_drawings'],
            height=Map.height.value
            )
    return output['all_drawings']

def show_metrics():
    area = 0
    cnt = 0
    if 'bboxes' in st.session_state and len(st.session_state['bboxes']) > 0:
        for bbox in st.session_state['bboxes']:
            area += bbox.area
        
            if bbox.preds is not None: 
                cnt += len(bbox.preds)

    density = cnt / area if area > 0 else 0
    cols = st.columns(3)
    with cols[0]:
        st.metric('Total Selected Area (Km²)', f"{area/1e6:.2f}")
    with cols[1]:
        st.metric('Total Count in Selected Area', cnt)
    with cols[2]:
        st.metric('Total Density of Coconutes in Selected Area(per Km²)', f"{density:.2f}")