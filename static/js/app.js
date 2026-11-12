// Default configs based on `config.yml` configuration
// Dense coconut estate in Sri Lanka's coconut triangle (~1,000 trees/km²),
// close enough to see individual trees.
const defaultCenter = [7.7955, 80.037];
const defaultZoom = 18;

const BOX_COLOR = '#f2b544';   // drawn boxes (matches the accent colour)
const TREE_COLOR = '#ff5a4f';  // detected trees: high contrast on green imagery

// Dense coconut areas, each checked by running the model on the spot
// (place names from OpenStreetMap reverse geocoding)
// (2,700 to 9,500 trees per km² in a 0.1 km² box).
const SPOTS = [
    { name: 'Pahala Mawathagama, Kurunegala, Sri Lanka', center: [7.7955, 80.037] },
    { name: 'Puliyampatti, Pollachi, Tamil Nadu, India', center: [10.68, 77.03] },
    { name: 'Indupalle, Konaseema, Andhra Pradesh, India', center: [16.57, 81.99] },
    { name: 'Cofradía de Morelos, Tecomán, Colima, Mexico', center: [18.88, -103.86] },
    { name: 'Nannamukku, Malappuram, Kerala, India', center: [10.7336, 76.0031] },
    { name: 'Anagondanahalli, Tiptur, Karnataka, India', center: [13.24, 76.46] },
];
let spotIndex = 0; // the map opens on SPOTS[0]

function goToNextSpot() {
    if (busy) return;
    setDrawMode(false);
    spotIndex = (spotIndex + 1) % SPOTS.length;
    const spot = SPOTS[spotIndex];
    mainMap.flyTo(spot.center, defaultZoom, { duration: 1.5 });
    setStatus(`Now at <strong>${spot.name}</strong>. Press <strong>Draw a box</strong> and drag over the trees, or <strong>Try another location</strong>.`);
}

let mainMap;
let statsMap;
let featureGroup;
let boxesGroup;

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
    initCoordsBar();

    // Add Search Box (Geocoder)
    L.Control.geocoder({
        defaultMarkGeocode: false,
        position: 'topright',
        placeholder: 'Search for a region...'
    }).on('markgeocode', function(e) {
        const bbox = e.geocode.bbox;
        mainMap.fitBounds(bbox);
    }).addTo(mainMap);

    // Drawn boxes and predicted trees (Clear removes both)
    boxesGroup = L.featureGroup().addTo(mainMap);
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
    drawButton = document.getElementById('draw-btn');
    drawButton.addEventListener('click', () => setDrawMode(!drawMode));
    document.getElementById('clear-btn').addEventListener('click', clearResults);
    document.getElementById('spot-btn').addEventListener('click', goToNextSpot);

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
        drawButton.setAttribute('aria-pressed', String(on));
        drawButton.querySelector('.btn-label').textContent = on ? 'Cancel' : 'Draw a box';
    }
    if (on) {
        setStatus('Drag on the map to draw a box (up to 0.5 km²). Lift your finger or release the mouse to start detecting.');
    } else if (!busy) {
        setStatus(idleMessage());
    }
}

// ---------------------------------------------------------------------------
// Coordinates bar under the map: pointer position on desktop, map centre
// otherwise (touch screens have no hover).
// ---------------------------------------------------------------------------
let coordsShown = null; // the LatLng currently displayed

function formatLatLng(ll) {
    const lat = `${Math.abs(ll.lat).toFixed(5)}° ${ll.lat >= 0 ? 'N' : 'S'}`;
    const lng = `${Math.abs(ll.lng).toFixed(5)}° ${ll.lng >= 0 ? 'E' : 'W'}`;
    return `${lat}, ${lng}`;
}

function showCoords(latlng, label) {
    coordsShown = latlng.wrap();
    document.getElementById('coords-label').textContent = label;
    document.getElementById('coords-value').textContent = formatLatLng(coordsShown);
}

function showCentre() {
    showCoords(mainMap.getCenter(), 'Map centre');
    document.getElementById('coords-zoom').textContent = `Zoom ${Math.round(mainMap.getZoom())}`;
}

function initCoordsBar() {
    const hover = window.matchMedia('(hover: hover)').matches;
    let pinned = null; // a clicked/tapped point stays shown until the next click

    const showResting = () => (pinned ? showCoords(pinned, 'Pinned') : showCentre());

    if (hover) {
        mainMap.on('mousemove', (e) => showCoords(e.latlng, 'Pointer'));
        mainMap.on('mouseout', showResting);
    }
    mainMap.on('click', (e) => {
        if (drawMode) return;
        pinned = e.latlng;
        showCoords(pinned, 'Pinned');
    });
    mainMap.on('move zoomend', () => {
        const label = document.getElementById('coords-label').textContent;
        if (label === 'Map centre') showCentre();
        document.getElementById('coords-zoom').textContent = `Zoom ${Math.round(mainMap.getZoom())}`;
    });
    showCentre();

    const copyBtn = document.getElementById('coords-copy');
    copyBtn.addEventListener('click', async () => {
        if (!coordsShown) return;
        const text = `${coordsShown.lat.toFixed(6)}, ${coordsShown.lng.toFixed(6)}`;
        try {
            await navigator.clipboard.writeText(text);
            copyBtn.textContent = 'Copied';
        } catch (err) {
            copyBtn.textContent = text; // clipboard blocked: show it to copy by hand
        }
        setTimeout(() => (copyBtn.textContent = 'Copy'), 1500);
    });
}

// ---------------------------------------------------------------------------
// Status line under the toolbar: tells the user what to do next / what happened.
// ---------------------------------------------------------------------------
let busy = false;

function setStatus(html, kind = '') {
    const el = document.getElementById('map-status');
    el.innerHTML = html;
    el.classList.toggle('is-error', kind === 'error');
    el.classList.toggle('is-success', kind === 'success');
}

function idleMessage() {
    return totalCount > 0 || totalArea > 0
        ? 'Draw another box to add to your count, or press <strong>Clear</strong> to start over.'
        : `Now at <strong>${SPOTS[spotIndex].name}</strong>. Press <strong>Draw a box</strong> and drag over the trees, or <strong>Try another location</strong>.`;
}

function fmt(n, digits = 0) {
    return n.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function clearResults() {
    setDrawMode(false);
    boxesGroup.clearLayers();
    featureGroup.clearLayers();
    totalArea = 0;
    totalCount = 0;
    updateMetrics();
    setStatus(idleMessage());
}

function onDrawPointerDown(e) {
    if (!drawMode || drawing || !e.isPrimary || e.button > 0) return;
    if (e.target.closest('.leaflet-control')) return; // buttons, search box
    e.preventDefault();
    mainMap.getContainer().setPointerCapture(e.pointerId);
    const start = mainMap.mouseEventToLatLng(e);
    const rect = L.rectangle(L.latLngBounds(start, start), { color: BOX_COLOR, weight: 2 }).addTo(mainMap);
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
        mainMap.removeLayer(layer);
        setStatus(`That box is ${fmt(areaSqM / 1e6, 2)} km². Please draw one under 0.5 km².`, 'error');
        return;
    }
    mainMap.removeLayer(layer);
    layer.setStyle({ color: BOX_COLOR, weight: 2, fillOpacity: 0.05 });
    boxesGroup.addLayer(layer);

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
                e.layer.setStyle({ color: '#ff7a6b', fillColor: '#ff7a6b' }); // too big
                if (drawTooltip) {
                    drawTooltip.setContent(`Area: ${tempAreaKm2.toFixed(3)} Km²<br/><span style="color:#ff7a6b;font-weight:bold;">Too big: keep it under 0.5 km²</span>`);
                }
            } else {
                e.layer.setStyle({ color: BOX_COLOR, fillColor: BOX_COLOR });
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
    
    document.getElementById('metric-area').textContent = fmt(areaKm2, 3);
    document.getElementById('metric-count').textContent = fmt(totalCount);
    document.getElementById('metric-density').textContent = fmt(density);
    document.getElementById('clear-btn').disabled = totalArea === 0 && totalCount === 0;
}

async function submitInference(geojson, layer) {
    const overlay = document.getElementById('loading-overlay');
    overlay.classList.remove('hidden');
    busy = true;
    drawButton.disabled = true;
    setStatus('Detecting trees in your box…');
    
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
        const n = features.length;
        setStatus(
            n > 0
                ? `<strong>Found ${fmt(n)} tree${n === 1 ? '' : 's'}</strong> in ${fmt(turf.area(geojson) / 1e6, 3)} km². Draw another box to add more, or press <strong>Clear</strong>.`
                : 'No coconut trees found in that box. Try an area where tree crowns are clearly visible, or press <strong>Try another location</strong>.',
            n > 0 ? 'success' : ''
        );
        
        // Draw predictions as circles
        features.forEach(feat => {
            const coords = feat.geometry.coordinates;
             L.circle([coords[1], coords[0]], {
                color: TREE_COLOR, 
                fill: false,      
                weight: 2,        
                radius: 3         
            }).addTo(featureGroup);
        });

        // Update statistics live
        await updateStats();

    } catch (err) {
        console.error("Error during inference API call:", err);
        setStatus(err.userMessage || "Something went wrong while detecting trees. Please try again.", 'error');
        // Revert area if inference fails
        totalArea -= turf.area(geojson);
        updateMetrics();
        boxesGroup.removeLayer(layer);
    } finally {
        overlay.classList.add('hidden');
        busy = false;
        drawButton.disabled = false;
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
        document.getElementById('stat-countries').textContent = fmt(data.countries.length);
        document.getElementById('stat-total-trees').textContent = fmt(data.metrics.total_trees_detected);
        document.getElementById('stat-locations').textContent = fmt(data.metrics.locations_covered);
        
        // Populate table
        const tbody = document.querySelector('#countries-table tbody');
        tbody.innerHTML = ''; // clear previous data
        data.countries
            .sort((a, b) => b.trees_detected - a.trees_detected)
            .forEach(c => {
                const tr = tbody.insertRow();
                tr.insertCell().textContent = c.country;
                tr.insertCell().textContent = fmt(c.trees_detected);
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
