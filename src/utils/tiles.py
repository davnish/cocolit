"""Fetch XYZ map tiles into an in-memory georeferenced image and cut it into patches.

Replaces rasvec's tms_to_geotiff + patchify_raster on the inference path: no GeoTIFFs
are written, tiles are fetched and decoded concurrently, and the mosaic is uint8.
The tile math, crop and georeferencing match rasvec, so detections are unchanged.
"""

import concurrent.futures
import io
import math
from dataclasses import dataclass
from typing import Iterator

import httpx
import numpy as np
from PIL import Image

from src.utils.mercator import deg2num, to_3857  # noqa: F401  (re-exported)

SATELLITE_URL = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
TILE_SIZE = 256
RETRIES = 3


@dataclass
class GeoImage:
    """RGB uint8 image (H, W, 3) georeferenced in EPSG:3857 metres."""

    array: np.ndarray
    left: float  # x of the top-left corner
    top: float  # y of the top-left corner
    pixel_width: float
    pixel_height: float  # positive; y decreases going down


@dataclass
class Patch:
    row: int
    col: int
    array: np.ndarray  # (size, size, 3) uint8, BGR as ultralytics expects for numpy input
    left: float
    top: float


def _get_tile(client: httpx.Client, url: str) -> bytes | None:
    for attempt in range(RETRIES):
        try:
            response = client.get(url)
            break
        except httpx.TransportError:
            if attempt == RETRIES - 1:
                raise
    if response.status_code == 404:
        return None  # missing tile: leave that area black, as rasvec does
    response.raise_for_status()  # other errors must fail loudly, not become black areas
    return response.content or None


def _decode(tile: bytes) -> np.ndarray:
    with Image.open(io.BytesIO(tile)) as im:
        return np.asarray(im.convert("RGB"))


@dataclass
class MosaicPlan:
    """Tiles to fetch for a bbox, and how the stitched tiles crop to the exact bbox."""

    zoom: int
    tx0: int  # first tile column / row (inclusive)
    ty0: int
    tx1: int  # last tile column / row (exclusive)
    ty1: int
    crop_x: int  # top-left of the bbox inside the stitched tiles, in pixels
    crop_y: int
    width: int  # bbox size in pixels
    height: int
    left: float  # EPSG:3857 georeferencing of the cropped image
    top: float
    pixel_width: float
    pixel_height: float

    @classmethod
    def for_bounds(cls, bounds: list[float], zoom: int = 19) -> "MosaicPlan":
        """[west, south, east, north] in degrees; same rounding as rasvec's finish_picture."""
        west, south, east, north = bounds
        x0, y0 = deg2num(south, west, zoom)
        x1, y1 = deg2num(north, east, zoom)
        x0, x1 = sorted([x0, x1])
        y0, y1 = sorted([y0, y1])
        tx0, ty0 = math.floor(x0), math.floor(y0)
        width, height = round(TILE_SIZE * (x1 - x0)), round(TILE_SIZE * (y1 - y0))
        xp0, yp0 = to_3857(south, west)
        xp1, yp1 = to_3857(north, east)
        return cls(
            zoom=zoom,
            tx0=tx0,
            ty0=ty0,
            tx1=math.ceil(x1),
            ty1=math.ceil(y1),
            crop_x=round(TILE_SIZE * (x0 - tx0)),
            crop_y=round(TILE_SIZE * (y0 - ty0)),
            width=width,
            height=height,
            left=min(xp0, xp1),
            top=max(yp0, yp1),
            pixel_width=abs(xp1 - xp0) / width,
            pixel_height=abs(yp1 - yp0) / height,
        )

    @property
    def tile_count(self) -> int:
        return (self.tx1 - self.tx0) * (self.ty1 - self.ty0)

    def tile_rows_for(self, row: int, size: int) -> range:
        """Tile rows (relative to ty0) covering patch row `row` of the cropped image."""
        top = self.crop_y + row * size
        bottom = min(self.crop_y + self.height, top + size)
        return range(top // TILE_SIZE, -(-bottom // TILE_SIZE))


def _download(
    plan: MosaicPlan, client: httpx.Client, workers: int, url: str
) -> Iterator[tuple[int, np.ndarray]]:
    """Fetch every tile into one uint8 canvas, row-major.

    Yields (completed_tile_row, canvas) each time a whole tile row has landed, in
    any order; the same canvas object is filled in place throughout.
    """
    cols = plan.tx1 - plan.tx0
    canvas = np.zeros(((plan.ty1 - plan.ty0) * TILE_SIZE, cols * TILE_SIZE, 3), np.uint8)
    remaining = [cols] * (plan.ty1 - plan.ty0)

    def fetch(x: int, y: int) -> tuple[int, int, np.ndarray | None]:
        tile = _get_tile(client, url.format(x=x, y=y, z=plan.zoom))
        return x, y, None if tile is None else _decode(tile)

    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        # Row-major submission so the top rows (the first patches) arrive first.
        futures = [
            pool.submit(fetch, x, y)
            for y in range(plan.ty0, plan.ty1)
            for x in range(plan.tx0, plan.tx1)
        ]
        try:
            for future in concurrent.futures.as_completed(futures):
                x, y, tile = future.result()
                r = y - plan.ty0
                if tile is not None:
                    oy, ox = r * TILE_SIZE, (x - plan.tx0) * TILE_SIZE
                    h, w = tile.shape[:2]
                    canvas[oy : oy + h, ox : ox + w] = tile
                remaining[r] -= 1
                if remaining[r] == 0:
                    yield r, canvas
        finally:
            for future in futures:
                future.cancel()


def fetch_mosaic(
    bounds: list[float],
    client: httpx.Client,
    zoom: int = 19,
    workers: int = 16,
    url: str = SATELLITE_URL,
) -> GeoImage:
    """Download the tiles covering [west, south, east, north] (degrees) into one image."""
    plan = MosaicPlan.for_bounds(bounds, zoom)
    canvas = None
    for _, canvas in _download(plan, client, workers, url):
        pass
    return GeoImage(
        array=canvas[plan.crop_y : plan.crop_y + plan.height, plan.crop_x : plan.crop_x + plan.width],
        left=plan.left,
        top=plan.top,
        pixel_width=plan.pixel_width,
        pixel_height=plan.pixel_height,
    )


def stream_patches(
    plan: MosaicPlan,
    client: httpx.Client,
    size: int = 640,
    workers: int = 16,
    url: str = SATELLITE_URL,
) -> Iterator[Patch]:
    """Like iter_patches(fetch_mosaic(...)), but yields each patch row as soon as its
    tiles have arrived, so the model can run while later tiles are still downloading."""
    rows = math.ceil(plan.height / size)
    done = [False] * (plan.ty1 - plan.ty0)
    image = None
    next_row = 0
    for tile_row, canvas in _download(plan, client, workers, url):
        done[tile_row] = True
        if image is None:
            image = GeoImage(
                array=canvas[plan.crop_y : plan.crop_y + plan.height, plan.crop_x : plan.crop_x + plan.width],
                left=plan.left,
                top=plan.top,
                pixel_width=plan.pixel_width,
                pixel_height=plan.pixel_height,
            )
        while next_row < rows and all(done[r] for r in plan.tile_rows_for(next_row, size)):
            yield from _row_patches(image, next_row, size)
            next_row += 1


def _row_patches(image: GeoImage, i: int, size: int) -> Iterator[Patch]:
    cols = math.ceil(image.array.shape[1] / size)
    for j in range(cols):
        window = image.array[i * size : (i + 1) * size, j * size : (j + 1) * size]
        patch = np.zeros((size, size, 3), np.uint8)
        patch[: window.shape[0], : window.shape[1]] = window[..., ::-1]  # RGB -> BGR
        yield Patch(
            row=i,
            col=j,
            array=patch,
            left=image.left + j * size * image.pixel_width,
            top=image.top - i * size * image.pixel_height,
        )


def patch_grid(image: GeoImage, size: int = 640) -> tuple[int, int]:
    height, width = image.array.shape[:2]
    return math.ceil(height / size), math.ceil(width / size)


def iter_patches(image: GeoImage, size: int = 640) -> Iterator[Patch]:
    """Yield size×size BGR patches row by row, zero-padding the right/bottom edges."""
    rows, _ = patch_grid(image, size)
    for i in range(rows):
        yield from _row_patches(image, i, size)
