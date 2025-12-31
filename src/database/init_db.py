from sqlmodel import SQLModel
from src.database.connection import engine
from src.database.model import BoundingBox, Pred, Feedback  # Import models for metadata


def create_db(engine):
    SQLModel.metadata.create_all(engine)

if __name__ == "__main__":
    create_db(engine)
