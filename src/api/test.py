import requests
import geopandas as gpd


def get_response() -> None:
    url = "http://127.0.0.1:8000/predict"

    json = {
        "xmin": 80.00295370817186,
        "ymin": 7.5521705091205416,
        "xmax": 80.00529795885087,
        "ymax": 7.553680785799453,
    }

    response = requests.post(url, json=json)
    data = response.json()["predictions"]
    gdf = gpd.GeoDataFrame.from_features(data["features"])
    return gdf

if __name__ == "__main__":
    gdf = get_response()
    print(gdf)

    # example_geojson_
    # array = {'type': 'Feature', 'properties': {}, 'geometry': {'type': 'Polygon', 'coordinates': [[[80.018299, 7.555792], [80.018299, 7.557355], [80.021324, 7.557355], [80.021324, 7.555792], [80.018299, 7.555792]]]}}
    