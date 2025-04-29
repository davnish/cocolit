import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import shape



def get_shapefile(data):
      """
      Convert GeoJSON to Shapefile
      """
      # Convert the GeoJSON to a shapely geometry
      geometry = shape(data['geometry'])
      
      # Create a GeoDataFrame
      # This conversion is done to convert the geometry to a planar geometry
      # which will help us to calculate the area and other planar operations
      gdf = gpd.GeoDataFrame(geometry=[geometry], crs="EPSG:4326").to_crs(epsg=3857)
      
      # Save the GeoDataFrame as a shapefile
      return gdf


if __name__ == "__main__":

   data = {"type":"Feature",
   "properties":{},
   "geometry":{
      "type":"Polygon",
      "coordinates":[[[-85.078125,38.61687],[-85.078125,41.771312],
                     [-81.430664,41.771312],[-81.430664,38.61687],
                     [-85.078125,38.61687]]]
                     }}
   
   gdf = get_shapefile(data)
   print(gdf.crs)  # Uncommented to check the coordinate reference system
   gdf.to_file("output.shp", driver='ESRI Shapefile')

   # geometry = shape(data['geometry'])

   # gdf = gpd.GeoDataFrame(geometry = [geometry], crs="EPSG:4326")
   # gdf.plot()
   # plt.show()
# print(gdf)