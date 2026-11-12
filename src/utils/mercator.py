"""Web Mercator (EPSG:3857) helpers; pure math, no geo libraries."""

import math

EARTH_RADIUS = 6378137.0


def deg2num(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Fractional XYZ tile coordinates of a WGS84 point."""
    lat_r = math.radians(lat)
    n = 2**zoom
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n
    return x, y


def to_3857(lat: float, lon: float) -> tuple[float, float]:
    x = math.radians(lon) * EARTH_RADIUS
    y = math.log(math.tan(math.radians(45 + lat / 2.0))) * EARTH_RADIUS
    return x, y
