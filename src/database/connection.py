from sqlmodel import create_engine
import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

@st.cache_resource
def get_engine():
    if os.getenv("local_database"):
        connection_string = os.getenv("local_database")
    elif os.environ.get("db_conn_host"):
        SERVER = os.environ["db_conn_host"]
        DATABASE = os.environ["db_conn_database"]
        USERNAME = os.environ["db_conn_user"]
        PASSWORD = os.environ["db_conn_password"]
    else:
        return None
    
    connection_string = f"postgresql://{USERNAME}:{PASSWORD}@{SERVER}/{DATABASE}"
    engine = create_engine(connection_string)
    return engine




engine = get_engine()

