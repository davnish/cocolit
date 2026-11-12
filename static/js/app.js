// Default configs based on `config.yml` configuration
const defaultCenter = [7.550186, 79.88214];
const defaultZoom = 15;

let mainMap;
let statsMap;
let featureGroup;

let totalArea = 0;
let totalCount = 0;

let drawTooltip = null;

// Initialize Main Map
function initMainMap() {
    mainMap = L.map('main-map', { zoomControl: false }).setView(defaultCenter, defaultZoom);
    
    // Add Google Satellite TileLayer (replace with actual if URL changes)
    L.tileLayer('https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}', {
        attribution: 'Google Satellite',
        maxZoom: 20
    }).addTo(mainMap);

    // Box tool: press the button, then drag a box with a finger, mouse or pen.
    initBoxDraw();

    // Add Search Box (Geocoder)
    L.Control.geocoder({
        defaultMarkGeocode: false,
        position: 'topright',
        placeholder: 'Search for a region...'
    }).on('markgeocode', function(e) {
        const bbox = e.geocode.bbox;
        mainMap.fitBounds(bbox);
    }).addTo(mainMap);

    // Feature group to hold predictions
    featureGroup = L.featureGroup().addTo(mainMap);

}

// ---------------------------------------------------------------------------
// Drag-to-draw box. Pointer events cover mouse, touch and pen with one code
// path; while the tool is on, map panning/zooming is off so a drag draws.
// ---------------------------------------------------------------------------
let drawMode = false;
let drawButton = null;
let drawing = null; // { pointerId, start: LatLng, startPoint: Point, rect }

function initBoxDraw() {
    const BoxControl = L.Control.extend({
        options: { position: 'topleft' },
        onAdd() {
            const bar = L.DomUtil.create('div', 'leaflet-bar');
            drawButton = L.DomUtil.create('a', 'draw-box-btn', bar);
            drawButton.href = '#';
            drawButton.title = 'Draw a box (drag on the map)';
            drawButton.setAttribute('role', 'button');
            drawButton.setAttribute('aria-pressed', 'false');
            drawButton.setAttribute('aria-label', 'Draw a box');
            drawButton.innerHTML =
                '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">' +
                '<rect x="4" y="4" width="16" height="16" fill="none" stroke="currentColor" ' +
                'stroke-width="2" stroke-dasharray="3 2"/></svg>';
            L.DomEvent.disableClickPropagation(bar);
            L.DomEvent.on(drawButton, 'click', (e) => {
                L.DomEvent.preventDefault(e);
                setDrawMode(!drawMode);
            });
            return bar;
        }
    });
    new BoxControl().addTo(mainMap);

    const el = mainMap.getContainer();
    el.addEventListener('pointerdown', onDrawPointerDown);
    el.addEventListener('pointermove', onDrawPointerMove);
    el.addEventListener('pointerup', onDrawPointerUp);
    el.addEventListener('pointercancel', cancelDrawing);
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && drawMode) setDrawMode(false);
    });
}

function setDrawMode(on) {
    drawMode = on;
    cancelDrawing();
    const handlers = [mainMap.dragging, mainMap.touchZoom, mainMap.doubleClickZoom, mainMap.boxZoom];
    handlers.forEach((h) => (on ? h.disable() : h.enable()));
    const el = mainMap.getContainer();
    el.classList.toggle('drawing-box', on);
    if (drawButton) {
        drawButton.classList.toggle('active', on);
        drawButton.setAttribute('aria-pressed', String(on));
    }
}

function onDrawPointerDown(e) {
    if (!drawMode || drawing || !e.isPrimary || e.button > 0) return;
    if (e.target.closest('.leaflet-control')) return; // buttons, search box
    e.preventDefault();
    mainMap.getContainer().setPointerCapture(e.pointerId);
    const start = mainMap.mouseEventToLatLng(e);
    const rect = L.rectangle(L.latLngBounds(start, start), { color: '#3388ff', weight: 2 }).addTo(mainMap);
    drawTooltip = L.tooltip({ permanent: true, direction: 'right', className: 'draw-tooltip' })
        .setLatLng(start)
        .setContent("Area: 0.000 Km²")
        .addTo(mainMap);
    drawing = { pointerId: e.pointerId, start, startPoint: mainMap.mouseEventToContainerPoint(e), rect };
}

function onDrawPointerMove(e) {
    if (!drawing || e.pointerId !== drawing.pointerId) return;
    e.preventDefault();
    const latlng = mainMap.mouseEventToLatLng(e);
    drawing.rect.setBounds(L.latLngBounds(drawing.start, latlng));
    updateLiveArea({ layer: drawing.rect }, latlng);
}

function onDrawPointerUp(e) {
    if (!drawing || e.pointerId !== drawing.pointerId) return;
    const { rect, startPoint } = drawing;
    const moved = startPoint.distanceTo(mainMap.mouseEventToContainerPoint(e));
    drawing = null;
    removeDrawTooltip();
    if (moved < 10) {
        // A tap, not a drag: nothing to submit.
        mainMap.removeLayer(rect);
        return;
    }
    setDrawMode(false);
    onBoxDrawn(rect);
}

function cancelDrawing() {
    if (drawing) {
        mainMap.removeLayer(drawing.rect);
        drawing = null;
    }
    removeDrawTooltip();
}

function removeDrawTooltip() {
    if (drawTooltip) {
        mainMap.removeLayer(drawTooltip);
        drawTooltip = null;
    }
}

// A finished box: check its size, then send it to inference.
async function onBoxDrawn(layer) {
    const geojson = layer.toGeoJSON();
    const areaSqM = turf.area(geojson);
    if (areaSqM / 1000000 > 0.5) {
        alert("The selected area is too large! Please decrease the size below 0.5 Km².");
        mainMap.removeLayer(layer);
        return;
    }

    totalArea += areaSqM;
    updateMetrics();

    await submitInference(geojson, layer);
}

function updateLiveArea(e, latlng) {
    if (!e.layer || !e.layer.toGeoJSON) return;
    try {
        const geojson = e.layer.toGeoJSON();
        
        if (geojson.geometry.type === 'Polygon' && geojson.geometry.coordinates[0].length >= 4) {
            const tempArea = turf.area(geojson);
            const tempAreaKm2 = tempArea / 1000000;
            const displayKm2 = ((totalArea / 1000000) + tempAreaKm2).toFixed(3);
            
            // Update global dashboard
            document.getElementById('metric-area').textContent = displayKm2;
            
            // Update tooltip text and layer color based on size
            if (tempAreaKm2 > 0.5) {
                e.layer.setStyle({ color: '#ef4444', fillColor: '#ef4444' }); // Red
                if (drawTooltip) {
                    drawTooltip.setContent(`Area: ${tempAreaKm2.toFixed(3)} Km²<br/><span style="color:#ef4444;font-weight:bold;">can you please decrease the size 🥺</span>`);
                }
            } else {
                e.layer.setStyle({ color: '#3388ff', fillColor: '#3388ff' }); // Blue
                if (drawTooltip) {
                    drawTooltip.setContent(`Area: ${tempAreaKm2.toFixed(3)} Km²<br/><span style="font-size:0.85em;color:#94a3b8;">Release to finish</span>`);
                }
            }
        }
        
        // Update tooltip position near mouse
        if (drawTooltip && latlng) {
            drawTooltip.setLatLng(latlng);
        }
    } catch (err) {
        // ignore incomplete polygon errors during drawing
    }
}

function updateMetrics() {
    const areaKm2 = totalArea / 1000000;
    const density = areaKm2 > 0 ? totalCount / areaKm2 : 0;
    
    document.getElementById('metric-area').textContent = areaKm2.toFixed(3);
    document.getElementById('metric-count').textContent = totalCount;
    document.getElementById('metric-density').textContent = density.toFixed(2);
}

async function submitInference(geojson, layer) {
    const overlay = document.getElementById('loading-overlay');
    overlay.classList.remove('hidden');
    
    try {
        const response = await fetch('/api/inference', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(geojson)
        });
        
        if (!response.ok) {
            let message = "Failed to get predictions. Please try again.";
            if (response.status === 429) {
                message = "Too many requests. Please wait a few seconds and try again.";
            } else if (response.status === 422) {
                const body = await response.json().catch(() => ({}));
                if (typeof body.detail === "string") message = body.detail;
            }
            const error = new Error(message);
            error.userMessage = message;
            throw error;
        }
        
        const data = await response.json();
        const features = data.features || [];
        
        totalCount += features.length;
        updateMetrics();
        
        // Draw predictions as circles
        features.forEach(feat => {
            const coords = feat.geometry.coordinates;
             L.circle([coords[1], coords[0]], {
                color: '#ef4444', 
                fill: false,      
                weight: 2,        
                radius: 3         
            }).addTo(featureGroup);
        });

        // Update statistics live
        await updateStats();

    } catch (err) {
        console.error("Error during inference API call:", err);
        alert(err.userMessage || "Failed to get predictions. Please try again.");
        // Revert area if inference fails
        totalArea -= turf.area(geojson);
        updateMetrics();
        mainMap.removeLayer(layer);
    } finally {
        overlay.classList.add('hidden');
    }
}

let heatLayer = null;

// Initialize Statistics Map
function initStatsMap() {
    // default center from stats_ui configs
    const statsCenter = [7.58, 80.70]; 
    const statsZoom = 6;
    
    // We don't disable zoom control here if user wants to explore
    statsMap = L.map('heatmap-map').setView(statsCenter, statsZoom);
    
    // Esri Light Gray Canvas: keyless (CARTO basemaps now require an API key).
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ',
        maxZoom: 16
    }).addTo(statsMap);
}

// Fetch and update Stats section
async function updateStats() {
    try {
        const response = await fetch('/api/statistics');
        if (!response.ok) throw new Error("Stats fetch failed");
        
        const data = await response.json();
        
        // Update summary digits
        document.getElementById('stat-countries').textContent = data.countries.length;
        document.getElementById('stat-total-trees').textContent = data.metrics.total_trees_detected;
        document.getElementById('stat-locations').textContent = data.metrics.locations_covered;
        
        // Populate table
        const tbody = document.querySelector('#countries-table tbody');
        tbody.innerHTML = ''; // clear previous data
        data.countries.forEach(c => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${c.country}</td><td>${c.trees_detected}</td>`;
            tbody.appendChild(tr);
        });
        
        // Remove old heat layer if it exists
        if (heatLayer && statsMap.hasLayer(heatLayer)) {
            statsMap.removeLayer(heatLayer);
        }
        
        // Add heatmap layer
        const heatPoints = data.heatmap.map(p => [p.lat, p.lng, 1]); // 1 is intensity
        if (heatPoints.length > 0) {
           heatLayer = L.heatLayer(heatPoints, {
               radius: 12, // match config
               blur: 20,
               maxZoom: 17
           }).addTo(statsMap);
        }
        
    } catch (err) {
        console.error("Failed to load statistics:", err);
    }
}

// Run on load
document.addEventListener('DOMContentLoaded', () => {
    initMainMap();
    initStatsMap();
    updateStats();
});
