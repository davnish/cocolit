from .exceptions import InvalidBBox

def valid_bbox(bbox : list) -> bool:
    """Check if the bounding box is valid."""

    # if bbox area is more than 5 km2
    if bbox.area.iloc[0] > 5e6:
        raise InvalidBBox("Bounding box area exceeds the maximum limit of 5 km2.")
    # if bbox area is less than 0.1 km2
    elif bbox.area.iloc[0] < 1e4:
        raise InvalidBBox("Bounding box area is less than the minimum limit of 0.1 km2.")

