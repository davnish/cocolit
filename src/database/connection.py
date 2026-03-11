from sqlmodel import create_engine
from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv()

@lru_cache()
def get_engine():
    if os.getenv("local_database"):
        connection_string = os.getenv("local_database")
    elif os.environ.get("POSTGRES_HOST"):
        SERVER = os.environ["POSTGRES_HOST"]
        DATABASE = os.environ["POSTGRES_DATABASE"]
        USERNAME = os.environ["POSTGRES_USERNAME"]
        PASSWORD = os.environ["POSTGRES_PASSWORD"]
        connection_string = f"postgresql://{USERNAME}:{PASSWORD}@{SERVER}/{DATABASE}"
    elif os.environ.get("db_conn_host"):
        SERVER = os.environ.get("db_conn_host")
        DATABASE = os.environ.get("db_conn_database")
        USERNAME = os.environ.get("db_conn_user")
        PASSWORD = os.environ.get("db_conn_password")
        connection_string = f"postgresql://{USERNAME}:{PASSWORD}@{SERVER}/{DATABASE}"
    else:
        return None
    
    engine = create_engine(connection_string)
    return engine




engine = get_engine()

