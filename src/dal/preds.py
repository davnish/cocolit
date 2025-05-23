from sqlmodel import Session
from geopandas import GeoDataFrame
from shapely.wkt import dumps
from datetime import datetime
from src.database.model import BoundingBox, Feedback, Pred
from src.database.connection import engine
import geopandas as gpd
from pathlib import Path


def preds_bbox_to_database(bbox: GeoDataFrame, preds: GeoDataFrame) -> None:
    with Session(engine) as session:
        bbox = BoundingBox(
            datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            geometry=dumps(bbox.loc[0, "geometry"]),
        )
        for _, pred in preds.iterrows():
            pred = Pred(conf=pred["conf"], geometry=dumps(pred["geometry"]), bbox=bbox)
            session.add(pred)
            if pred.conf < 0.3:
                session.add(Feedback(bbox=bbox, pred=pred))
        session.commit()


def read_data()->tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    query = "SELECT * FROM pred"
    pred = gpd.read_postgis(query, con=engine, crs=3857, geom_col="geometry").to_crs(
        4326
    )
    country_shp = Path("data", "countries", "world-administrative-boundaries.shp")
    country = gpd.read_file(country_shp)
    return pred, country


if __name__ == "__main__":
    pass
