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
    L.tileLayer('http://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}', {
        attribution: 'Google Satellite',
        maxZoom: 20
    }).addTo(mainMap);

    // Add Geoman controls
    mainMap.pm.addControls({
        position: 'topleft',
        drawMarker: false,
        drawCircleMarker: false,
        drawPolyline: false,
        drawRectangle: true,
        drawPolygon: false,
        drawCircle: false,
        drawText: false,
        editMode: false,
        dragMode: false,
        cutPolygon: false,
        removalMode: true
    });
    
    // Feature group to hold predictions
    featureGroup = L.featureGroup().addTo(mainMap);

    // Event: Real-time area calculation while drawing
    mainMap.on('pm:drawstart', ({ workingLayer }) => {
        // Init tooltip bound near cursor
        drawTooltip = L.tooltip({ permanent: true, direction: 'right', className: 'draw-tooltip' })
            .setLatLng(mainMap.getCenter())
            .setContent("Area: 0.00 Km²")
            .addTo(mainMap);

        workingLayer.on('pm:vertexadded', (e) => updateLiveArea({ layer: workingLayer }, null));
        mainMap.on('mousemove', (e) => {
            if (workingLayer._latlngs) {
                 updateLiveArea({ layer: workingLayer }, e.latlng);
            }
        });
    });
    
    mainMap.on('pm:drawend', () => {
        if (drawTooltip) {
            mainMap.removeLayer(drawTooltip);
            drawTooltip = null;
        }
    });

    // Event: Shape drawn (send to inference)
    mainMap.on('pm:create', async (e) => {
        const layer = e.layer;
        const geojson = layer.toGeoJSON();
        
        // Final area calc for this shape
        const areaSqM = turf.area(geojson);
        totalArea += areaSqM;
        updateMetrics();

        // Send inference request
        await submitInference(geojson, layer);
    });
    
    mainMap.on('pm:remove', (e) => {
        window.location.reload();
    })
}

function updateLiveArea(e, latlng) {
    if (!e.layer || !e.layer.toGeoJSON) return;
    try {
        const geojson = e.layer.toGeoJSON();
        
        if (geojson.geometry.type === 'Polygon' && geojson.geometry.coordinates[0].length >= 4) {
            const tempArea = turf.area(geojson);
            const displayKm2 = ((totalArea + tempArea) / 1000000).toFixed(3);
            
            // Update global dashboard
            document.getElementById('metric-area').textContent = displayKm2;
            
            // Update tooltip text
            if (drawTooltip) {
                drawTooltip.setContent(`Area: ${(tempArea / 1000000).toFixed(3)} Km²`);
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
        
        if (!response.ok) throw new Error("Inference failed");
        
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
        alert("Failed to get predictions. See console.");
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
    
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
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
