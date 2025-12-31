from sqlmodel import create_engine
import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

@st.cache_resource
def get_engine():
    engine = create_engine(connection_string)
    return engine

if os.getenv("local_database"):
    connection_string = os.getenv("local_database")
else:
    SERVER = os.environ["db_conn_host"]
    DATABASE = os.environ["db_conn_database"]
    USERNAME = os.environ["db_conn_user"]
    PASSWORD = os.environ["db_conn_password"]

    connection_string = f"postgresql://{USERNAME}:{PASSWORD}@{SERVER}/{DATABASE}"


engine = get_engine()

