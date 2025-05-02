import folium
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium
from pipelines.inference import InferencePipeline
from src.bbox import BBox
from pathlib import Path
import torch
import geopandas as gpd
import logging
import os

st.set_page_config(layout="wide")

# os.environ["STREAMLIT_WATCHER_TYPE"] = "none"
torch.classes.__path__ = []

logger = logging.getLogger(__name__)
filehandler = logging.FileHandler('log/streamlit.log')
filehandler.setLevel(logging.INFO)

logger.addHandler(filehandler)

st.title("CocoDet")

@st.cache_resource
def load_inference(model_path):
    inference = InferencePipeline(model_path)
    return inference

model_path="models/train/weights/best.onnx"
inference = load_inference(model_path)

m = folium.Map(location=[7.551830,80.020504], zoom_start=15, tiles = None)
tile = folium.TileLayer(
            tiles = 'http://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}',
            attr = 'Google Satellite',
            name = 'Satellite',
            overlay = False,
            control = True)


tile.add_to(m)

pt = folium.FeatureGroup(name = 'CocoTrees')

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

if 'bboxes' in st.session_state and len(st.session_state['bboxes']) > 0:
    try:
        # need to fix the bug of calling the inference every time the map changes. for e.g if zoom level changes.


        
        # logger.info(f"Got the shp {gdf}")

        for i in st.session_state['bboxes']:
            if i.preds is not None:
                trees = folium.GeoJson(i.preds, name='CocoTrees',
                                    marker=folium.Circle(radius=4, fill_color="orange", fill_opacity=0.1, color="orange", weight=1),
                                    highlight_function=lambda x: {"fillOpacity": 0.8},
                                    )
                pt.add_child(trees)
            


    except Exception as e:
            logger.error(f"Error {e}") 

c1, c2 = st.columns(2)

with c1:
    output =  st_folium(m, 
            feature_group_to_add=pt, 
            use_container_width=True,
            layer_control=layer_control,
            )

# output = update_map()
    logging.info(output)
with c2:
    area = 0
    if 'bboxes' in st.session_state and len(st.session_state['bboxes']) > 0:
        for i in st.session_state['bboxes']:
            area += i.area
        st.metric('Area', area)


# output = update_map()

# These lines are run after st_folium to get the ouput dict which consist the info of the bbox

all_drawings = output['all_drawings']


if output['all_drawings'] is not None and len(output['all_drawings'])>0:

    if len(st.session_state['bboxes'])>0 and output['all_drawings'][-1] == st.session_state['bboxes'][-1].data:
        pass
    else:
        st.session_state['bboxes'].append(inference.run(BBox(output['all_drawings'][-1])))
        st.rerun()

if (output['all_drawings'] is None or len(output['all_drawings'])==0):

    if 'bboxes' not in st.session_state: 
        st.session_state['bboxes'] = []
    elif len(st.session_state['bboxes'])>0:
        st.session_state['bboxes'] = []
        st.rerun()


