from sqlmodel import create_engine, SQLModel, Session, select
import streamlit as st
from .model import BoundingBox


@st.cache_resource
def get_engine():
    engine = create_engine(connection_string)
    return engine


SERVER = st.secrets.db_conn['host']
DATABASE = st.secrets.db_conn['database']
USERNAME = st.secrets.db_conn['user']
PASSWORD = st.secrets.db_conn['password']

connection_string = f"postgresql://{USERNAME}:{PASSWORD}@{SERVER}/{DATABASE}"

engine = get_engine()


def test_connection():
    try:
        with Session(engine) as session:
            session.exec(select(BoundingBox).limit(1))
            return True
    except Exception as e:
        return False


def create_db():
    SQLModel.metadata.create_all(engine)
