import streamlit as st
from src.data_struct.feedbox import FeedBox
from src.data_struct.queue import Queue


def init_feedback(config: dict) -> None:
    if "queue" not in st.session_state:
        st.session_state["queue"] = Queue()

    # Dynamically Fixing the no of feedboxes to show

    positions = len(st.session_state["queue"])
    columns = config["feedback_ui"]["columns"]
    feedboxes_no = columns if positions >= columns else positions

    with st.container():
        cols = st.columns(feedboxes_no)
        for idx in range(1, feedboxes_no + 1):
            with cols[idx - 1]:
                pos = f"{idx}_feedbox"
                if (
                    pos not in st.session_state
                    or st.session_state.get(f"{pos}_no")
                    or st.session_state.get(f"{pos}_yes")
                ):
                    id_bounds: list = st.session_state["queue"].dequeue_enqueue()
                    st.session_state[pos] = id_bounds
                else:
                    id_bounds: list = st.session_state[pos]

                feedbox = FeedBox(pos, id_bounds)
                feedbox.make_feedbox()
