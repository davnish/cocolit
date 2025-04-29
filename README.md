# CocoDet


# Propose
- A full production grade ML project to detect coconut tree

## Output:
    - Users will visually be able to see the detected coconut tree over the basemap
## User Input: 
    - Coordinates of a bounding box (top-left corner, bottom-right corner)
    - Shapefile of the selected region. Consisting only the extent of the region.
    - Selecting regions through the baseman drawing over the map.

## Proposed Features

- Will ask the users if for feedback and if the probable bounding box consists a coconut tree or not.
    - This can be done in a (Yes/No) format.
- Experimenting with providing a downloading button of the vector.

## Proposed Requirements
 
### Hardware
    - Cloud
        - For storing data and model
        - For model finetuinning and inference

### Software
- MLflow
- Python (Rasterio, GeoPandas, Pytorch, logger, Optuna)

#### Experiment with
    - Kubeflow
    - Airflow
    - DVC#### Models
    - YOLOv11

### Data
- Label data of detected coconuts.


## Proposed Date
    - One Month till 7th May.

## Timeline
- To be completed.



## Procedure

### project
- I have compeleted building a `prepare_data` pipeline which takes the input of the bbox and some other imput for paths and create the dataset for the model for training

### Streamlit
- I am using folium
    - the procdure for the streamlit is, I going to select a bounding box from the map, and then input this bounding box to the model which will detect coconute and the given area.



