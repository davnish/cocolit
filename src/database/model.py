from sqlmodel import SQLModel, Field, Column, Relationship
from geoalchemy2 import Geometry
from typing import Optional
from .connection import engine


class BoundingBox(SQLModel, table=True):
    id : int | None = Field(default = None, primary_key=True)
    datetime : str
    geometry : str = Field(sa_column=Column(Geometry('POLYGON', srid=3857)))
    preds : list["Pred"] = Relationship(back_populates="bbox")
    feedbacks : list["Feedback"] = Relationship(back_populates="bbox", cascade_delete=True)

class Pred(SQLModel, table=True):
    id : int | None = Field(default = None, primary_key=True)
    id_bbox : int = Field(foreign_key="boundingbox.id", ondelete="CASCADE")

    conf : float
    geometry : str = Field(sa_column=Column(Geometry('POINT', srid=3857)))
    bbox : BoundingBox = Relationship(back_populates="preds")
    feedback : Optional["Feedback"] = Relationship(back_populates="pred", cascade_delete=True,sa_relationship_kwargs={'uselist': False})
    
class Feedback(SQLModel, table=True):
    id : int | None = Field(default=None, primary_key=True, index=True)
    yes : int = Field(default=0)
    no : int = Field(default=0)
    id_pred : int = Field(foreign_key="pred.id", ondelete="CASCADE")
    id_bbox : int = Field(foreign_key = "boundingbox.id", ondelete="CASCADE")
    bbox : BoundingBox = Relationship(back_populates="feedbacks")
    pred : Pred = Relationship(back_populates="feedback")

def create_db():
    SQLModel.metadata.create_all(engine)


if __name__ == "__main__":
    pass

    