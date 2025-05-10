
import streamlit as st
import torch
from src.feedback import init_feedback
from src.streamlit.maps_ui import get_map, init_boxes, add_predictions, get_inference, get_output, show_metrics, load_inference
from pathlib import Path
from enum import Enum

torch.classes.__path__ = []
st.set_page_config(layout='wide')

class Model(Enum):
    path : Path = Path("models/train/weights/best.onnx")
inference = load_inference(Model.path.value)


st.title("Coco:blue[lit] :palm_tree:")
st.caption('Lets detect some coconuts! :sunglasses:')

m, layer_control = get_map()

pt = add_predictions() 

with st.container(height=450, border=False):
    all_drawings = get_output(m, pt, layer_control)

show_metrics()

get_inference(all_drawings, inference)

init_boxes(all_drawings)

st.header("Feedbacks :seedling:")
st.caption("Help the current model improve by giving suggestions.")
st.caption("Can you recognize the below images at coconut trees.")

init_feedback()