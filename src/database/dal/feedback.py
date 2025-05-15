from ..model import Feedback, Pred
from ..connection import engine
from sqlmodel import Session, select, func


class FeedbackDAO:
    def get_id_wbuffer(self):
        with Session(engine) as session:
            try:
                buffer_size : float = 15
                buffer = func.ST_AsText(func.ST_Transform(func.ST_Envelope(func.ST_Buffer(Pred.geometry, buffer_size)), 4326))
                statement = select(Feedback.id_pred, buffer).join(Pred, isouter=True)
                res = session.exec(statement)
                return res.all()
            except Exception as e:
                session.rollback()

    
    def get_all_id_geometry(self):
        with Session(engine) as session:
            try:
                geometry = func.ST_AsText(Pred.geometry)
                statement = select(Feedback.id_pred, geometry).join(Pred, isouter=True).order_by(func.random()).limit(50)
                res = session.exec(statement).all()
                return res
            except:
                session.rollback()
                raise

    def update_by_id(self, id: int, column: str) -> None:
        with Session(engine) as session:
            try:
                statement = select(Feedback).where(Feedback.id_pred == id)
                res = session.exec(statement).one()
                if column == 'yes':
                    res.yes += 1
                else:
                    res.no += 1
                session.add(res)
                session.commit()
            except Exception as e:
                session.rollback()
                raise


if __name__ == "__main__":
    pass
    from time import perf_counter

    st = perf_counter()
    q = FeedbackDAO().get_id_wbuffer()
    ed = perf_counter()
    print(ed - st)

