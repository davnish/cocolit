from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Union


from pydantic import BaseModel

from src.exceptions.exceptions import BBoxTooBig, BBoxTooSmall
from src.utils.mercator import to_3857

# geopandas/shapely are only needed for drawn GeoJSON shapes (frontend). The
# inference service only sees BBoxBounds, so it never imports them.
if TYPE_CHECKING:
    from geopandas import GeoDataFrame


class BBoxBounds(BaseModel):
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def to_list(self) -> list:
        """Return bounds as a list."""
        return [self.xmin, self.ymin, self.xmax, self.ymax]

    def to_bounds_dict(self) -> dict:
        """Return bounds as a dictionary."""
        return {
            "xmin": self.xmin,
            "ymin": self.ymin,
            "xmax": self.xmax,
            "ymax": self.ymax,
        }

    def area_3857(self) -> float:
        """Area in EPSG:3857 m²; a lon/lat box is an axis-aligned rectangle there."""
        x0, y0 = to_3857(self.ymin, self.xmin)
        x1, y1 = to_3857(self.ymax, self.xmax)
        return abs(x1 - x0) * abs(y1 - y0)

    @classmethod
    def from_geojson(cls, data: dict) -> "BBoxBounds":
        from shapely.geometry import shape

        geometry = shape(data["geometry"])
        bounds = geometry.bounds
        return cls(
            xmin=bounds[0],
            ymin=bounds[1],
            xmax=bounds[2],
            ymax=bounds[3],
        )


@dataclass
class BBox:
    data: Union[dict, BBoxBounds]
    # values to be initialized post creation
    gdf: "GeoDataFrame | None" = field(init=False, default=None) # EPSG:3857 shape; only for GeoJSON input
    area: float = field(init=False, default=0) # Area of the bbox in square meters
    bounds: list = field(init=False, default_factory=list) # Bounds of the bbox as [xmin, ymin, xmax, ymax]
    preds: Any = field(init=False, default=None) # pipelines.inference.Predictions, set by InferencePipeline.run
    timings: dict = field(init=False, default_factory=dict) # Per-stage wall times (s), filled by InferencePipeline.run

    def __post_init__(self) -> None:
        if isinstance(self.data, dict):
            self.gdf = self.geojson_to_gdf(self.data)
            self.bounds = self.gdf.to_crs(4326).bounds.to_numpy().tolist()[0]
            self.area = self.gdf.geometry.iloc[0].area
        else:
            self.bounds = self.data.to_list()
            self.area = self.data.area_3857()

    def geojson_to_gdf(self, data: dict) -> "GeoDataFrame":
        """
        Convert GeoJSON to a GeoDataFrame.

        Geographical coordinates (EPSG:4326) are converted to EPSG:3857 (metres),
        so the area can be computed for validation.
        """
        from geopandas import GeoDataFrame
        from shapely.geometry import shape

        geometry = shape(data["geometry"])
        gdf = GeoDataFrame(geometry=[geometry], crs="EPSG:4326").to_crs(3857)
        return gdf

    def valid_bbox(self) -> None:
        """Raise if the bounding box is too big or too small."""
        # more than 5 km²
        if self.area > 5e6:
            raise BBoxTooBig
        # less than 625 m²
        elif self.area < 625:
            raise BBoxTooSmall

    def to_dict(self) -> dict:
        return {
            'xmin': self.bounds[0],
            'ymin': self.bounds[1],
            'xmax': self.bounds[2],
            'ymax': self.bounds[3],
        }
