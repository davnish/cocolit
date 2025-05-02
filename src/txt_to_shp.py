from shapely.geometry import box, Point
import os
import glob
import rasterio as rio
import geopandas as gpd
import pandas as pd

def txt_to_shp(txt_dir, img_dir, shp_dir):

    file_name = os.path.splitext(os.path.basename(txt_dir))[0]
    
    with rio.open(os.path.join(img_dir, f"{file_name}.tif")) as src:
        # profile = src.profile
        bounds = src.bounds
        crs = src.crs
        # raster_extent = box(*bounds)
        top_left_corner = (bounds.left, bounds.top)
        bottom_right_corner = (bounds.right, bounds.bottom)
    
    df = pd.read_csv(txt_dir, delimiter = " ", names = ['class', 'x', 'y', 'width', 'height'])  

    df['x'] = df['x'] * (bottom_right_corner[0] - top_left_corner[0]) + top_left_corner[0]
    df['y'] = top_left_corner[1] - df['y'] * (top_left_corner[1] - bottom_right_corner[1])

    df['centroid'] = [Point(x, y) for x, y in zip(df.x, df.y)]

    gdf = gpd.GeoDataFrame(geometry = df['centroid'], crs = crs)
    
    # gdf['geometry'] = gdf.geometry.apply(lambda geom: point_to_bbox(geom, buffer_x, buffer_y))
    output_filepath = os.path.join(shp_dir, f"{file_name}.shp")
    gdf.to_file(output_filepath, driver="ESRI Shapefile")

    return gdf

def concat(shp_dir, output_dir):
    df = None
    for i in glob.glob(os.path.join(shp_dir, "*.shp")):
        df_curr = gpd.read_file(i)
        if df is None:
            df = df_curr
        else:
            df = pd.concat([df, df_curr], ignore_index = True)
            
    gdf = gpd.GeoDataFrame(df)
    gdf.to_file(os.path.join(output_dir, "prediction.shp"), driver="ESRI Shapefile")

if __name__ == "__main__":
    pass

