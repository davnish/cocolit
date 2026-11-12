import io
import math

import httpx
import numpy as np
import pytest
from PIL import Image

from src.utils.tiles import (
    TILE_SIZE,
    GeoImage,
    MosaicPlan,
    deg2num,
    fetch_mosaic,
    iter_patches,
    patch_grid,
    stream_patches,
    to_3857,
)

ZOOM = 19
# ~0.1 km² around the integration-test estate; spans several tiles and partial edges.
BOUNDS = [80.0194, 7.8084, 80.0224, 7.8112]


def tile_colour(x: int, y: int) -> tuple[int, int, int]:
    return (x % 251, y % 251, 7)


def png(colour: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (TILE_SIZE, TILE_SIZE), colour).save(buf, format="PNG")
    return buf.getvalue()


def parse(url: httpx.URL) -> tuple[int, int]:
    # SATELLITE_URL has no "?": the params live in the path, e.g. /vt/lyrs=s&x=1&y=2&z=19
    params = dict(part.split("=") for part in url.path.rsplit("/", 1)[1].split("&"))
    return int(params["x"]), int(params["y"])


def client_for(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def tile_range(bounds):
    west, south, east, north = bounds
    x0, y0 = deg2num(south, west, ZOOM)
    x1, y1 = deg2num(north, east, ZOOM)
    x0, x1 = sorted([x0, x1])
    y0, y1 = sorted([y0, y1])
    return x0, y0, x1, y1


def pixel_of_tile_centre(bounds, x, y):
    """(row, col) in the cropped image of tile (x, y)'s centre, or None if cropped out."""
    x0, y0, x1, y1 = tile_range(bounds)
    cx, cy = round(TILE_SIZE * (x0 - math.floor(x0))), round(TILE_SIZE * (y0 - math.floor(y0)))
    row = (y - math.floor(y0)) * TILE_SIZE + TILE_SIZE // 2 - cy
    col = (x - math.floor(x0)) * TILE_SIZE + TILE_SIZE // 2 - cx
    return row, col


def visible_tiles(bounds, image):
    x0, y0, x1, y1 = tile_range(bounds)
    for x in range(math.floor(x0), math.ceil(x1)):
        for y in range(math.floor(y0), math.ceil(y1)):
            row, col = pixel_of_tile_centre(bounds, x, y)
            if 0 <= row < image.array.shape[0] and 0 <= col < image.array.shape[1]:
                yield x, y, row, col


def test_fetch_mosaic_places_tiles_and_crops_like_rasvec():
    image = fetch_mosaic(
        BOUNDS, client_for(lambda r: httpx.Response(200, content=png(tile_colour(*parse(r.url))))),
        zoom=ZOOM, workers=4,
    )

    x0, y0, x1, y1 = tile_range(BOUNDS)
    assert image.array.dtype == np.uint8
    assert image.array.shape == (round(TILE_SIZE * (y1 - y0)), round(TILE_SIZE * (x1 - x0)), 3)

    checked = 0
    for x, y, row, col in visible_tiles(BOUNDS, image):
        assert tuple(image.array[row, col]) == tile_colour(x, y)
        checked += 1
    assert checked >= 4

    # Georeferencing identical to rasvec.tms_to_geotiff (EPSG:3857 metres).
    west, south, east, north = BOUNDS
    xp0, yp0 = to_3857(south, west)
    xp1, yp1 = to_3857(north, east)
    assert image.left == pytest.approx(xp0)
    assert image.top == pytest.approx(yp1)
    assert image.pixel_width * image.array.shape[1] == pytest.approx(xp1 - xp0)
    assert image.pixel_height * image.array.shape[0] == pytest.approx(yp1 - yp0)


def test_missing_tile_is_left_black():
    x0, y0, _, _ = tile_range(BOUNDS)
    missing = (math.floor(x0) + 1, math.floor(y0) + 1)

    def handler(request):
        if parse(request.url) == missing:
            return httpx.Response(404)
        return httpx.Response(200, content=png((200, 200, 200)))

    image = fetch_mosaic(BOUNDS, client_for(handler), zoom=ZOOM, workers=4)

    for x, y, row, col in visible_tiles(BOUNDS, image):
        expected = (0, 0, 0) if (x, y) == missing else (200, 200, 200)
        assert tuple(image.array[row, col]) == expected


def test_transport_errors_are_retried():
    calls = {}

    def handler(request):
        key = parse(request.url)
        calls[key] = calls.get(key, 0) + 1
        if calls[key] == 1:
            raise httpx.ConnectError("flaky", request=request)
        return httpx.Response(200, content=png((10, 20, 30)))

    image = fetch_mosaic(BOUNDS, client_for(handler), zoom=ZOOM, workers=4)

    assert all(n == 2 for n in calls.values())
    assert tuple(image.array[0, 0]) == (10, 20, 30)


def test_server_errors_raise():
    with pytest.raises(httpx.HTTPStatusError):
        fetch_mosaic(BOUNDS, client_for(lambda r: httpx.Response(500)), zoom=ZOOM, workers=4)


def test_iter_patches_pads_edges_converts_to_bgr_and_georeferences():
    rgb = np.zeros((700, 1300, 3), np.uint8)
    rgb[..., 0] = 255  # pure red in RGB
    image = GeoImage(array=rgb, left=1000.0, top=5000.0, pixel_width=0.5, pixel_height=0.25)

    patches = list(iter_patches(image, size=640))

    assert patch_grid(image, 640) == (2, 3)
    assert [(p.row, p.col) for p in patches] == [(i, j) for i in range(2) for j in range(3)]
    for p in patches:
        assert p.array.shape == (640, 640, 3)
        assert p.left == pytest.approx(1000.0 + p.col * 640 * 0.5)
        assert p.top == pytest.approx(5000.0 - p.row * 640 * 0.25)

    full = patches[0].array
    assert tuple(full[0, 0]) == (0, 0, 255)  # red in BGR
    # bottom-right patch covers rows 640..699 and cols 1280..1299, rest is zero padding
    corner = patches[-1].array
    assert tuple(corner[59, 19]) == (0, 0, 255)
    assert corner[60:].sum() == 0
    assert corner[:, 20:].sum() == 0


# ~1 km²: several patch rows, so streaming has rows to hand out early.
BIG_BOUNDS = [80.0160, 7.8050, 80.0250, 7.8140]


def test_stream_patches_equals_fetch_then_slice():
    handler = lambda r: httpx.Response(200, content=png(tile_colour(*parse(r.url))))
    expected = list(iter_patches(fetch_mosaic(BIG_BOUNDS, client_for(handler), zoom=ZOOM, workers=4)))
    plan = MosaicPlan.for_bounds(BIG_BOUNDS, ZOOM)

    streamed = list(stream_patches(plan, client_for(handler), workers=4))

    assert len(expected) > 3
    assert [(p.row, p.col) for p in streamed] == [(p.row, p.col) for p in expected]
    for a, b in zip(streamed, expected):
        assert np.array_equal(a.array, b.array)
        assert (a.left, a.top) == (b.left, b.top)


def test_stream_patches_yields_first_row_before_download_finishes():
    plan = MosaicPlan.for_bounds(BIG_BOUNDS, ZOOM)
    fetched = []

    def handler(request):
        fetched.append(parse(request.url))
        return httpx.Response(200, content=png((1, 2, 3)))

    first = next(stream_patches(plan, client_for(handler), workers=1))

    assert first.row == 0 and first.col == 0
    assert len(fetched) < plan.tile_count
