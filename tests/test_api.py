from fastapi.testclient import TestClient
from main import app
import pytest

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "Cocolit: Coconut Tree Detection" in response.text

def test_api_statistics_mocked(mocker):
    # Mock the config dict since it's used globally in main
    mocker.patch("main.config", {"statistics_ui": {"center": [0,0], "zoom": 1}})
    
    # Mock the database read_data so we don't need a real db for tests
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import Point
    
    pred_data = {
        "id": [10, 11],
        "id_bbox": [1, 1],
        "conf": [0.9, 0.8],
        "geometry": [Point(80.0, 7.0), Point(80.1, 7.1)]
    }
    pred_gdf = gpd.GeoDataFrame(pd.DataFrame(pred_data), geometry="geometry")
    
    # Mock countries
    country_data = {
        "name": ["Sri Lanka"],
        "geometry": [Point(80.5, 7.5).buffer(5)] # Large buffer to intersect
    }
    country_gdf = gpd.GeoDataFrame(pd.DataFrame(country_data), geometry="geometry")
    
    mocker.patch("main.read_data", return_value=(pred_gdf, country_gdf))
    
    response = client.get("/api/statistics")
    assert response.status_code == 200
    
    data = response.json()
    assert "heatmap" in data
    assert len(data["heatmap"]) == 2
    assert "metrics" in data
    assert data["metrics"]["locations_covered"] == 1
    assert data["metrics"]["total_trees_detected"] == 2
    
def test_inference_invalid_url(mocker):
    import os
    mocker.patch.dict(os.environ, clear=True) # Ensure it is not set for this test
    
    response = client.post("/api/inference", json={
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [[[0,0], [1,0], [1,1], [0,1], [0,0]]]},
        "properties": {}
    })
    
    assert response.status_code == 500
    assert "INFERENCE_URL not set" in response.json()["detail"]
