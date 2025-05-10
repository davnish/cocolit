
import streamlit as st
from streamlit_folium import st_folium
from src.feedbox import FeedBox, Queue
from src.logger_config import setup_logger



logger = setup_logger('feedback', 'feedback.log')

def init_feedback():

    if 'queue' not in st.session_state:
        st.session_state['queue'] = Queue()

    feedboxes_no = 6

    with st.container():
        cols = st.columns(feedboxes_no)
        for idx in range(1, feedboxes_no + 1):


            with cols[idx-1]:
                pos = f'{idx}_feedbox'
                if (pos not in st.session_state or st.session_state.get(f'{pos}_no') or st.session_state.get(f'{pos}_yes')):
                    logger.info(f'Setting up column {pos}')
                    id_bounds: list = st.session_state['queue'].dequeue_enqueue()
                    st.session_state[pos] = id_bounds
                    logger.info(f'Got id {id_bounds}')

                else:
                    id_bounds : list = st.session_state[pos]

                # breakpoint()
                feedbox = FeedBox(pos, id_bounds)
                feedbox.make_feedbox()



