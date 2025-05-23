import requests
import geopandas as gpd


def get_respose() -> None:
    url = "http://127.0.0.1:8000/predict"

    json = {
        "xmin": 80.00295370817186,
        "ymin": 7.5521705091205416,
        "xmax": 80.00529795885087,
        "ymax": 7.553680785799453,
    }

    respose = requests.post(url, json=json)
    data = respose.json()["predictions"]
    gpd.GeoDataFrame.from_features(data["features"])