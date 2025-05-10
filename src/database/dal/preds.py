from sqlmodel import Session
from geopandas import GeoDataFrame
from shapely.wkt import dumps
from datetime import datetime
from ..model import BoundingBox, Feedback, Pred
from ..connection import engine


def preds_bbox_to_database(bbox: GeoDataFrame, preds : GeoDataFrame) -> None:
    with Session(engine) as session:
        bbox = BoundingBox(datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S'), geometry = dumps(bbox.loc[0,'geometry']))
        for _, pred in preds.iterrows():
            pred = Pred(conf=pred['conf'], geometry=dumps(pred['geometry']), bbox = bbox)
            session.add(pred)
            if pred.conf<0.2:
                session.add(Feedback(bbox = bbox, pred = pred))
        session.commit()