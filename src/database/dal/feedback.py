from ..model import Feedback, Pred
from ..connection import engine
from sqlmodel import Session, select, func

class FeedbackDAO:
    def get_id_wbuffer(self):
        with Session(engine) as session:
            buffer_size : float = 15
            buffer = func.ST_AsText(func.ST_Transform(func.ST_Envelope(func.ST_Buffer(Pred.geometry, buffer_size)), 4326))
            statement = select(Feedback.id_pred, buffer).join(Pred, isouter=True)
            res = session.exec(statement)

        return res.all()
    
    def get_id_geometry(self):
        with Session(engine) as session:
            geometry = func.ST_AsText(Pred.geometry)
            statement = select(Feedback.id_pred, geometry).join(Pred, isouter=True).order_by(func.random()).limit(50)
            res = session.exec(statement).all()
        return res
    
    def update_by_id(self, id: int, column: str) -> None:
        with Session(engine) as session:
            statement = select(Feedback).where(Feedback.id_pred == id)
            res = session.exec(statement).one()
            if column == 'yes':
                res.yes += 1
            else:
                res.no += 1

            session.add(res)
            session.commit()

if __name__ == "__main__":
    pass
    from time import perf_counter

    st = perf_counter()
    q = FeedbackDAO().get_id_wbuffer()
    ed = perf_counter()
    print(ed - st)


    

    

    # gdf.set_crs("EPSG:3857", inplace=True)

    # print(gdf)
# def to_geodataframe(self, feedbacks: List[Feedback  | BoundingBox | Pred]) -> gpd.GeoDataFrame:
#         """Converts a list of Feedback objects to a GeoDataFrame."""
#         data = []
#         geometry = []
#         crs = "EPSG:3857"  # Adjust if needed

#         for feedback in feedbacks:
#             if feedback.pred and feedback.pred.geometry:
#                 try:
#                     point_geom = wkt.loads(feedback.pred.geometry)
#                     data.append({
#                         "feedback_id": feedback.id,
#                         "yes": feedback.yes,
#                         "no": feedback.no,
#                         "pred_id": feedback.id_pred,
#                         "bbox_id": feedback.id_bbox,
#                         # Add other relevant attributes
#                     })
#                     geometry.append(point_geom)
#                 except Exception as e:
#                     print(f"Error parsing geometry for Feedback ID {feedback.id}: {e}")

#         gdf = gpd.GeoDataFrame(data, geometry=geometry, crs=crs)
#         return gdf

