import folium
import streamlit as st
from folium.plugins import Draw
from streamlit_folium import st_folium
from pipelines.inference import inference
from src.geojson_to_shapefile import get_shapefile
from shapely.geometry import shape


import geopandas as gpd



st.title("CocoDet")


tile = folium.TileLayer(
            tiles = 'http://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}',
            attr = 'Google Satellite',
            name = 'Satellite',
            overlay = False,
            control = True)

m = folium.Map(location=[23.437,94.012], zoom_start=4, tiles = tile)

Draw(
    export=False,
    position="topleft",
    draw_options={
        "polyline": False,
        "poly": False,
        "circle": False,
        "polygon": False,
        "marker": False,
        "circlemarker": False,
        "rectangle": True,
        "edit": False,
    },
).add_to(m)

c1, c2 = st.columns(2)
with c1:
    output = st_folium(m, width=700, height=500)

with c2:
    st.write(output['last_active_drawing'])

    if output['last_active_drawing'] is not None:

        bbox = output['last_active_drawing']

        shp = inference(bbox)