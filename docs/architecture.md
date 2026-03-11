# Frontend Architecture & Migration Documentation

## Overview

The Cocolit application's frontend has been entirely rewritten, migrating away from the restrictive Streamlit + Folium framework. The new architecture uses a **FastAPI** backend that acts as a secure Backend-For-Frontend (BFF), communicating natively with the underlying PostgreSQL database and k3s `inference-service`. The frontend is now a **Vanilla JS / HTML / CSS** application loaded immediately by FastAPI, utilizing Leaflet.js directly for mapping.

This migration was driven by the necessity for real-time interactivity—specifically, dynamically calculating and displaying the area of a bounding box *while* the user is actively drawing it—which is impossible using Streamlit’s static rerender cycle.

---

## Architectural Changes

### 1. Removing Streamlit dependencies
The entire Streamlit runtime was expunged. The `src/ui/` module was deleted, removing `maps_ui.py`, `statistics_ui.py`, and `feedback_ui.py`. The `requirements_streamlit.txt` was updated to replace Streamlit specifics with standard web server packages (`fastapi`, `uvicorn`, `python-multipart`).
  - **Commit artifact changes:** Removed unused imports (like `@st.cache_resource`) and Streamlit session state management from `src/database/connection.py`.

### 2. FastAPI Backend Setup
`main.py` is now the sole entry point to the application instance running via Uvicorn.

**Core Responsibilities of `main.py`:**
- **Static files:** Mounts the internal `static/` directory to serve our `index.html`, `style.css`, and `js/app.js` to the browser upon connection tracking.
- **REST Endpoints:** Exposes `/api/inference` and `/api/statistics` which wrap the removed logic from the old Streamlit UI component handlers using FastAPI routing.

### 3. Vanilla JS Frontend setup
The actual UI is decoupled from Python.

**Core files:**
- `static/index.html`: Defines the layout grids, metric box structures, and map container `DIVs` (e.g., `#main-map` and `#heatmap-map`).
- `static/style.css`: Uses pure CSS grid, flexbox, variables, and modern visual attributes (drop shadows, blur, custom tooltips) to match premium, dark mode design requirements. 
- `static/js/app.js`: Connects to `index.html` DOM elements, instantiates Leaflet interfaces on the specified DIVs, handles user inputs (drag/drawing behaviors using `Leaflet-Geoman`), and queries the REST Endpoints asynchronously to update the UI without needing to refresh.

---

## Flow of Data

### 1. The Main Map / Inference Request
When a user visits the URL:
1. They see the map configured in `app.js` (`initMainMap()`). 
2. As they drag a bounding box on the map via the rectangle tool, the plugin `Leaflet-Geoman` provides real-time boundary updates `(workingLayer._latlngs)`.
3. The JavaScript `updateLiveArea()` intercepts this event, converts the partial bounds to a complete rectangle temporarily using `Turf.js`, and calculates the area in real-time, displaying it in the floating tooltip.
4. When the user releases the mouse (`pm:create` event), `submitInference()` packs the bounding box GeoJSON into the body of an HTTP `POST` request to `/api/inference`.
5. The FastAPI backend endpoint recreates the `BBox` object from the python backend, ships that over HTTP to the *separate* internal K3s inference container.
6. The `inference-service` returns predicted locations in `EPSG:3857` (meters).
7. FastAPI writes this new prediction into PostgreSQL via `preds_bbox_to_database()` and internally transforms the predicted coordinates mathematically to `EPSG:4326` (Lat/Long degrees).
8. FastAPI responds to the frontend with the converted predicted locations as a GeoJSON collection.
9. `app.js` unpacks this GeoJSON data, counts the results, and applies an `L.circle()` around every Lat/Long location detected natively inside Leaflet over the map.

### 2. The Statistics / Heatmap Request
When the user visits the page natively, or instantly after the inference finishes running (detailed above):
1. `app.js` dynamically queries `GET /api/statistics`.
2. The FastAPI endpoint runs `read_data()` from `dal/preds.py` calling a spatial database SQL query using Geopandas over PostgreSQL that crosses over all historic `pred_data` points combined with global mapping country definitions. 
3. The endpoint sums up "totals per country" for the tables and returns an array of Latitude, Longitude objects corresponding precisely to where coconut trees were identified.
4. `app.js` interprets this output via `updateStats()`. It resets the DOM table injecting new rows matching the countries queried, and applies the `Leaflet.heat` plugin layer iteratively upon the secondary Map view showing colored regions scaling dynamically via tree density.

---

## Modifying the App - Where to Start

If you need to make changes to the app in the future, follow this index based on the issue type:

### UI Layout & Content adjustments
- **Where:** `static/index.html` 
- **Action:** Any textual alterations, headers, structural layout wrappers, or adding new dashboard sections.

### Visual Styling & Colors
- **Where:** `static/style.css` 
- **Action:** Modify the `:root` variables to change all colors universally. Adjust animations, class hover interactions, and responsive mobile resizing.

### Map Behaviors & Interactive Bug Fixes
- **Where:** `static/js/app.js` 
- **Action:** Adjust the size/color of the trees being rendered (`radius`, `color`, `weight` inside `L.circle`), modify when drawing terminates/starts, or handle API failure callbacks natively in JS.

### Python Business Logic & Database Setup
- **Where:** `main.py`
- **Action:** Modify or add a completely new `/api/{name}` data bridge route (Example: you want to query how many users use the tool daily).

### SQL and Data Analytics Functions
- **Where:** `src/dal/preds.py` or `src/database/model.py`
- **Action:** Adjusting the columns natively inserted or queried representing the actual saved state on the cloud backend database.
