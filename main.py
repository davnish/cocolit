
import streamlit as st
import torch
from src.model_config import Model
from streamlit_folium import st_folium
from src.database.connection import test_connection

st.set_page_config(layout='wide')
from src.streamlit.feedback_ui import init_feedback
from src.streamlit.maps_ui import get_map, init_boxes, add_predictions, get_inference, show_metrics, load_inference
from src.streamlit.statistics_ui import init_statistics

torch.classes.__path__ = []

inference = load_inference(Model.path.value)

if 'conn' not in st.session_state:
    conn = test_connection()

st.title("Coco:blue[lit] :palm_tree:")
st.caption('Lets detect some coconuts! :sunglasses:')

m, layer_control = get_map()

pt = add_predictions() 

with st.container(height=400, border=False):
    output = st_folium(m, 
            feature_group_to_add=pt, 
            use_container_width=True,
            layer_control=layer_control,
            returned_objects=['all_drawings'],
            height=350
            )
    all_drawings = output['all_drawings']

show_metrics()

get_inference(all_drawings, inference, conn)

init_boxes(all_drawings)


if conn:
    try:
        init_statistics()
    except Exception as e:
        st.error("Internal Error")
    try:
        st.header("Feedbacks :seedling:")
        st.caption("Help the current model improve by giving suggestions.")
        st.caption("Can you recognize the below images at coconut trees.")

        init_feedback()
    except Exception as e:
        st.error("Server Error")

