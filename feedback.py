# def download  
from pathlib import Path
from src.download import TMStoGeoTIFF
# from pipelines.
# import pandas as pd
import geopandas as gpd
import streamlit as st
from streamlit_folium import st_folium
import folium
import matplotlib.pyplot as plt
from shapely import wkt
import cv2
import numpy as np
import geopandas as gpd
from PIL import Image, ImageDraw
import rasterio as rio
from rasterio.warp import transform_bounds

st.set_page_config(layout='wide')
# breakpoint()

imlist = 'images/img1.tiff'

with st.container(height=400, border=False):

    cols = st.columns(5)
    for idx, col in enumerate(cols):
        with col:
            img = cv2.imread('images/img1.tiff', cv2.IMREAD_COLOR_RGB)
            # img = np.asarray(img)

            img = np.asarray(img)
            centroid = (img.shape[0]//2, img.shape[1]//2)
            img = cv2.circle(img, centroid, 16, (255,255,0), 1) 

            st.image(img, use_container_width=True, clamp=True)
            bcols = st.columns(2)

            with bcols[0]:
                st.button('Yes', key=f"{idx}_1", use_container_width=True, type='primary')
            with bcols[1]:
                st.button('No', key=f"{idx}_2", use_container_width=True)


########### Testing the Possibility of using small folium maps aligned horizontally


gdf = gpd.read_file('data/preds.shp')

gdf = gdf.iloc[[0]] 


height = 200
with st.container():

    mapcols = st.columns(5)

    for idx, mcol in enumerate(mapcols):

        with mcol:
            
            m = folium.Map(location=[gdf.geometry.iloc[0].y, gdf.geometry.iloc[0].x], zoom_start=20, tiles=None, zoom_control=False)
            tile = folium.TileLayer(
                        tiles = 'http://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}',
                        attr = 'Google Satellite',
                        name = 'Satellite',
                        overlay = False,
                        control = True)
            
            tile.add_to(m)
            pt = folium.FeatureGroup(name = 'CocoTrees')


            trees = folium.GeoJson(gdf, name='CocoTrees',
                                    marker=folium.Circle(radius=4, fill_color="orange", fill_opacity=0.1, color="orange", weight=1),
                                    highlight_function=lambda x: {"fillOpacity": 0.8},
                                    )
            
            
            pt.add_child(trees)
            st_folium(m, use_container_width=True, feature_group_to_add=pt, height = height, key=idx, pixelated=True)

            bcols = st.columns(2)

            with bcols[0]:
                st.button('Yes', key=f"{idx}_4", use_container_width=True, type='primary')
            with bcols[1]:
                st.button('No', key=f"{idx}_3", use_container_width=True)

# def feedbox():

#########################

###### Feeadback with imageoverlay

gdf = gpd.read_file('data/preds.shp')

gdf = gdf.iloc[[0]] 


height = 200
with st.container():

    mapcols = st.columns(5)

    for idx, mcol in enumerate(mapcols):

        with mcol:
            
            m = folium.Map(location=[gdf.geometry.iloc[0].y, gdf.geometry.iloc[0].x], zoom_start=21, tiles=None, zoom_control=False)
            tile = folium.TileLayer(
                        tiles = 'http://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}',
                        attr = 'Google Satellite',
                        name = 'Satellite',
                        overlay = False,
                        control = True)
            
            # tile.add_to(m)
            pt = folium.FeatureGroup(name = 'CocoTrees')


            trees = folium.GeoJson(gdf, name='CocoTrees',
                                    marker=folium.Circle(radius=4, fill_color="orange", fill_opacity=0.1, color="orange", weight=1),
                                    highlight_function=lambda x: {"fillOpacity": 0.8},
                                    )
            
            with rio.open('images/img1.tiff') as src:
                profile = src.crs
                bounds3857 = src.bounds
                data = src.read().transpose(2,1,0)

            bounds = transform_bounds(profile, "EPSG:4326", *bounds3857)
            # print(bounds_4326)
            # xmin, ymin, xmax, ymax = bounds_4326

            folium.raster_layers.ImageOverlay(
                image=data,
                name="image overlay",
                # opacity=1,
                bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
            ).add_to(m)

            pt.add_child(trees)
            st_folium(m, use_container_width=True, feature_group_to_add=pt,pixelated=False, height = height, key=f"{idx}_feed_")

            bcols = st.columns(2)

            with bcols[0]:
                st.button('Yes', key=f"{idx}_5", use_container_width=True, type='primary')
            with bcols[1]:
                st.button('No', key=f"{idx}_6", use_container_width=True)