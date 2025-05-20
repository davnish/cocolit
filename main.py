import streamlit as st
import torch
from streamlit_folium import st_folium
import yaml
import random

st.set_page_config(layout="wide")

from src.database.connection import engine
from configs.logger import setup_logger
from src.ui.feedback_ui import init_feedback
from src.ui.maps_ui import get_map, init_boxes, add_predictions
from src.ui.maps_ui import get_inference, show_metrics, load_inference
from src.ui.statistics_ui import init_statistics
from src.exceptions.exceptions import BBoxTooBig, BBoxTooSmall

with open("static/style.css") as f:
    st.write(f"<style>{f.read()}</style>", unsafe_allow_html=True)


@st.cache_data
def read_config():
    with open("configs/config.yml", "r") as f:
        config = yaml.safe_load(f)
        return config


config = read_config()

logger = setup_logger("main", "main.log")
torch.classes.__path__ = []


def set_random_center():
    centers = config["map_ui"]["centers"]
    idx = random.choice(range(len(centers)))
    st.session_state["center"] = centers[idx]


if "center" not in st.session_state:
    st.session_state["center"] = config["map_ui"]["centers"][0]
    st.session_state["location"] = config["map_ui"]["locations"][0]

if "zoom" not in st.session_state:
    st.session_state["zoom"] = config["map_ui"]["zoom"]

if "conn" not in st.session_state:
    try:
        with engine.connect() as conn:
            st.session_state["conn"] = True
    except Exception as e:
        st.session_state["conn"] = False
        logger.fatal(f"Database Server Down: {e}")

if "show_feedback" not in st.session_state:
    st.session_state["show_feedback"] = True

if "show_stats" not in st.session_state:
    st.session_state["show_stats"] = True

inference = load_inference(config["model"]["path"])

st.title("Coco:blue[lit] :palm_tree:")
st.write("Lets detect some coconuts! :sunglasses: ")
st.caption(
    "The map is default centered on 'Divulgasanga, Sri Lanka', chosen for its high density of coconut trees, allowing for more effective model testing. \
            To explore a new random location, click 'Next Place'. \
            To search for a specific location, tap the '🔍' icon in the top right corner of the map.\
            For guidance on getting started, tap 'Help?' below for a visual walkthrough."
)

helpers = st.columns([0.8, 1, 7])
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
                """
            )

        with guides[1]:
            st.video(
                config["map_ui"]["helper_vid"], autoplay=True, muted=True, loop=True
            )

with helpers[1]:
    if st.button("Next Place", icon=":material/mood:"):
        set_random_center()

        logger.info("Shifting Center")

m, layer_control = get_map(config)

pt = add_predictions(config)

with st.container():
    output = st_folium(
        m,
        center=st.session_state["center"],
        zoom=st.session_state["zoom"],
        returned_objects=["all_drawings"],
        feature_group_to_add=pt,
        use_container_width=True,
        layer_control=layer_control,
    )
    all_drawings = output["all_drawings"]

show_metrics()

init_boxes(all_drawings)

with helpers[2]:
    try:
        with st.spinner("Running Inference..", show_time=True):
            get_inference(all_drawings, inference, st.session_state["conn"])
    except BBoxTooSmall:
        st.warning("Bounding Box too small, increase the Size of bounding box")
    except BBoxTooBig:
        st.warning("Bounding Box too, big, decrease the size of bounding box")
    except Exception:
        st.error("There is some Internal Error. Please Referesh the app. :persevere:")
        logger.fatal(BBoxTooSmall, exc_info=True)


if st.session_state["conn"]:
    if st.session_state["show_stats"]:
        try:
            init_statistics(config)
        except Exception as e:
            st.session_state["show_stats"] = False
            logger.fatal(e, exc_info=True)

    if st.session_state["show_feedback"]:
        try:
            st.header("Feedbacks :seedling:")
            st.caption(
                "Help the current model improve by giving suggestions. Can you recognize the below images as coconut trees."
            )
            init_feedback(config)
        except Exception as e:
            st.session_state["show_feedback"] = False
            logger.fatal(e, exc_info=True)
