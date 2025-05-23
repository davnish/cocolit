from sqlmodel import create_engine, SQLModel
import streamlit as st
import os

@st.cache_resource
def get_engine():
    engine = create_engine(connection_string)
    return engine

if os.getenv("local_database"):
    connection_string = os.getenv("local_database")
else:
    SERVER = st.secrets.db_conn["host"]
    DATABASE = st.secrets.db_conn["database"]
    USERNAME = st.secrets.db_conn["user"]
    PASSWORD = st.secrets.db_conn["password"]

    connection_string = f"postgresql://{USERNAME}:{PASSWORD}@{SERVER}/{DATABASE}"


engine = get_engine()


def create_db():
    SQLModel.metadata.create_all(engine)
