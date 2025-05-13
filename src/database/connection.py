from sqlmodel import create_engine, SQLModel, Session, select
import streamlit as st
from .model import BoundingBox

host = st.secrets.db_conn['host']
database = st.secrets.db_conn['database']
user = st.secrets.db_conn['user']
password = st.secrets.db_conn['password']

connection_string = f"postgresql://{user}:{password}@{host}:5432/{database}"
print(connection_string)


# @st.cache_resource
def get_engine():
    engine = create_engine(connection_string)
    return engine

engine = get_engine()


def test_connection():
    try:
        with Session(engine) as session:
            session.exec(select(BoundingBox).limit(1))
            return True
    except Exception as e:
        return False


def create_db():
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
