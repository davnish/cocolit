from dataclasses import dataclass, field
from src.dal.feedback import FeedbackDAO
import geopandas as gpd


@dataclass
class Queue:
    id_bounds: list = field(default_factory=list)

    def __post_init__(self) -> None:
        id_geometry = FeedbackDAO().get_all_id_geometry()
        self.id_bounds.extend(self.get_id_bufferbounds(id_geometry))

    def get_id_bufferbounds(self, res: list) -> list:
        """This gives a structure to add the queue. e.g [id, [geometry]]"""
        gdf = gpd.GeoDataFrame(res, columns=["id", "geometry"])
        gdf["geometry"] = gpd.GeoSeries.from_wkt(gdf["geometry"], crs=3857)
        bounds = (
            gdf.set_geometry("geometry")
            .buffer(15)
            .to_crs(4326)
            .bounds.to_numpy()
            .tolist()
        )
        id_geometry = gdf["id"].to_numpy().tolist()
        id_bounds = [[_id, bound] for _id, bound in zip(id_geometry, bounds)]
        return id_bounds

    def enqueue(self, id_bound: list) -> None:
        self.id_bounds.append(id_bound)

    def dequeue(self) -> int | None:
        if self.id_bounds:
            return self.id_bounds.pop(0)
        return None

    def __len__(self) -> int:
        return len(self.id_bounds)

    def dequeue_enqueue(self) -> int:
        id_bound = self.dequeue()
        if id_bound is not None:
            self.enqueue(id_bound)
        return id_bound
