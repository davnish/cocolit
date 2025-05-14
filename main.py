
import streamlit as st
import torch
from streamlit_folium import st_folium
from pathlib import Path
from enum import Enum
import random
st.set_page_config(layout='wide')

from src.logger_config import setup_logger
from src.model_config import Model
from src.database.connection import test_connection
from src.streamlit.feedback_ui import init_feedback
from src.streamlit.maps_ui import get_map, init_boxes, add_predictions
from src.streamlit.maps_ui import get_inference, show_metrics, load_inference
from src.streamlit.statistics_ui import init_statistics
from src.exceptions import BBoxTooBig, BBoxTooSmall

logger = setup_logger('main', 'main.log')
torch.classes.__path__ = []

class Map(Enum):
    LOCATION : list[float] = [7.551830,80.020504]
    ZOOM: int = 15
    layergroup_name : str = 'Cocolit'
    HEIGHT : int = 350

if 'center' not in st.session_state:
    st.session_state['center'] = Map.LOCATION.value

if 'zoom' not in st.session_state:
    st.session_state['zoom'] = Map.ZOOM.value

if 'conn' not in st.session_state:
    # st.session_state['conn'] = test_connection()
    st.session_state['conn'] = False
    logger.info("Testing Connection")

inference = load_inference(Model.path.value)


st.title("Coco:blue[lit] :palm_tree:")
st.write('Lets detect some coconuts! :sunglasses: ')
st.caption('The current location is selected because this area has abundance of coconut trees \
           and you can test the model better here. You can tap the "Help?" button below to get a visual guide and "Next Place" to get to a random location to test the model.')


helpers = st.columns([0.8,1,7], border=False)
with helpers[0]:
    with st.popover("Help? :hugging_face:"):
        guides = st.columns(2)
        with guides[0]:
            st.subheader("Take a look at the video to get started :rocket:")
            st.write(
                """ 
                - Click on the rectangle icon on the left side of the map.
                - Drag along your interested region.
                - And... Done! :dancer:
                """)

        with guides[1]:
            st.video(Path('misc/help_vis.mov').as_posix(), autoplay=True, muted=True, loop=True)

with helpers[1]:
    if st.button('Next Place', icon=":material/mood:"):
        centers = [[11.2588, 75.780], [17.0050, 82.2400], [-12.9704, 38.5124], [10.2435, 106.3750]]
        selected = random.choice(centers)

        st.session_state['center'] = selected
        st.session_state['zoom'] = 15

        logger.info("Shifting Center")

m, layer_control = get_map()

pt = add_predictions() 

with st.container(height=400, border=False):
    output = st_folium(m, 
            center = st.session_state['center'],
            zoom=st.session_state['zoom'],
            height=Map.HEIGHT.value,
            returned_objects=['all_drawings'],
            feature_group_to_add=pt, 
            use_container_width=True,
            layer_control=layer_control
            )
    all_drawings = output['all_drawings']

show_metrics()

init_boxes(all_drawings)

with helpers[2]:
        try:
            with st.spinner("Running Inference..", show_time=True):
                get_inference(all_drawings, inference, st.session_state['conn'])

        except BBoxTooSmall:
            st.error("Bounding Box too small, Increase the Size of bounding box")
        except BBoxTooBig:
            st.error("Bounding Box too, big, decrease the size of bounding box")
        except Exception as e:
            st.error("There is some Internal Error. Please Referesh the app. :persevere:")


if st.session_state['conn']:
    try:
        init_statistics()
    except Exception as e:
        st.error("Internal Error")
        logger.error(e)
    try:
        st.header("Feedbacks :seedling:")
        st.caption("Help the current model improve by giving suggestions.")
        st.caption("Can you recognize the below images at coconut trees.")

        init_feedback()
    except Exception as e:
        st.error("Server Error")
        st.error(e)
        

