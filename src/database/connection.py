from sqlmodel import create_engine
import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

@st.cache_resource
def get_engine():
    if os.getenv("local_database"):
        connection_string = os.getenv("local_database")
    elif os.environ.get("POSTGRES_HOST"):
        SERVER = os.environ["POSTGRES_HOST"]
        DATABASE = os.environ["POSTGRES_DATABASE"]
        USERNAME = os.environ["POSTGRES_USERNAME"]
        PASSWORD = os.environ["POSTGRES_PASSWORD"]
        connection_string = f"postgresql://{USERNAME}:{PASSWORD}@{SERVER}/{DATABASE}"
    else:
        return None
    
    engine = create_engine(connection_string)
    return engine




engine = get_engine()

