/**
 * NER GIS Explorer - Frontend Map Controller
 * Built with MapLibre GL JS & PMTiles
 */

// 1. Initialize PMTiles Protocol
const protocol = new pmtiles.Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

// Configuration & State Extents
const NER_BOUNDS = [
  [88.013472, 21.941250], // Southwest [lng, lat]
  [97.411250, 29.461528]  // Northeast [lng, lat]
];

const STATE_BOUNDS = {
  "ALL": NER_BOUNDS,
  "Arunachal Pradesh": [[91.50, 26.60], [97.41, 29.46]],
  "Assam": [[89.70, 24.10], [96.00, 28.00]],
  "Manipur": [[93.00, 23.80], [94.80, 25.70]],
  "Meghalaya": [[89.80, 25.00], [92.80, 26.10]],
  "Mizoram": [[92.20, 21.94], [93.40, 24.50]],
  "Nagaland": [[93.30, 25.20], [95.30, 27.00]],
  "Sikkim": [[88.01, 27.00], [88.90, 28.10]],
  "Tripura": [[91.10, 22.90], [92.40, 24.50]]
};

// Unified Basemap Style (100% Free & Open - Zero API Keys Required)
const mapStyle = {
  version: 8,
  sources: {
    "osm-tiles": {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "Map data &copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors"
    },
    "esri-dark": {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      attribution: "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ"
    },
    "esri-sat": {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      attribution: "Tiles &copy; Esri, Maxar, Earthstar Geographics"
    },
    "opentopo": {
      type: "raster",
      tiles: ["https://tile.opentopomap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "Map data &copy; OSM contributors, SRTM | Map style: &copy; OpenTopoMap"
    }
  },
  layers: [
    { id: "base-osm", type: "raster", source: "osm-tiles", minzoom: 0, maxzoom: 19, layout: { visibility: "visible" } },
    { id: "base-dark", type: "raster", source: "esri-dark", minzoom: 0, maxzoom: 20, layout: { visibility: "none" } },
    { id: "base-satellite", type: "raster", source: "esri-sat", minzoom: 0, maxzoom: 20, layout: { visibility: "none" } },
    { id: "base-topo", type: "raster", source: "opentopo", minzoom: 0, maxzoom: 17, layout: { visibility: "none" } }
  ]
};

let currentBasemap = "osm";
let map;

// Initialize Map
function initMap() {
  map = new maplibregl.Map({
    container: "map",
    style: mapStyle,
    center: [92.7124, 25.7014],
    zoom: 6.5,
    minZoom: 4.5,
    maxZoom: 18,
    maxBounds: [[85.0, 20.0], [100.0, 31.0]]
  });

  map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
  map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-left");

  map.on("load", () => {
    addRasterOverlays();
    addVectorLayers();
    setupEventListeners();
  });

  // HUD Coordinate Tracker
  map.on("mousemove", (e) => {
    const coords = `${e.lngLat.lng.toFixed(3)}°E, ${e.lngLat.lat.toFixed(3)}°N`;
    document.getElementById("hudCoords").textContent = coords;
  });

  map.on("zoom", () => {
    document.getElementById("hudZoom").textContent = map.getZoom().toFixed(1);
  });
}

// 2. Add Georeferenced Terrain Raster Overlays (Web Mercator Aligned)
function addRasterOverlays() {
  // Web Mercator EPSG:3857 aligned corner coordinates [lng, lat]
  const rasterCoords = [
    [88.013472, 29.461528], // top-left
    [97.411317, 29.461528], // top-right
    [97.411317, 21.941150], // bottom-right
    [88.013472, 21.941150]  // bottom-left
  ];

  // A. Clean 30m Shaded Relief & Hypsometric DEM (Pure raster without titles/borders)
  map.addSource("source-terrain-relief", {
    type: "image",
    url: "hillshade_overlay.png",
    coordinates: rasterCoords
  });

  map.addLayer({
    id: "layer-terrain-relief",
    type: "raster",
    source: "source-terrain-relief",
    paint: {
      "raster-opacity": 0.65,
      "raster-resampling": "linear"
    }
  });

  // B. Clean Terrain Slope Heatmap (0° - 89° Color Relief)
  map.addSource("source-terrain-slope", {
    type: "image",
    url: "slope_overlay.png",
    coordinates: rasterCoords
  });

  map.addLayer({
    id: "layer-terrain-slope",
    type: "raster",
    source: "source-terrain-slope",
    layout: { visibility: "none" },
    paint: {
      "raster-opacity": 0.70,
      "raster-resampling": "linear"
    }
  });
}

// 3. Add Vector Layers from PMTiles
function addVectorLayers() {
  const pmtilesUrl = "ner_map.pmtiles";

  map.addSource("ner_pmtiles", {
    type: "vector",
    url: `pmtiles://${pmtilesUrl}`
  });

  // --- A. States Fill & Line ---
  map.addLayer({
    id: "layer-states-fill",
    type: "fill",
    source: "ner_pmtiles",
    "source-layer": "states",
    paint: {
      "fill-color": "#38BDF8",
      "fill-opacity": 0.04
    }
  });

  map.addLayer({
    id: "layer-states-line",
    type: "line",
    source: "ner_pmtiles",
    "source-layer": "states",
    paint: {
      "line-color": "#0369A1",
      "line-width": 2.4,
      "line-opacity": 0.95
    }
  });

  // --- B. Districts Line ---
  map.addLayer({
    id: "layer-districts-line",
    type: "line",
    source: "ner_pmtiles",
    "source-layer": "districts",
    minzoom: 5.5,
    paint: {
      "line-color": "#64748B",
      "line-width": 1.1,
      "line-dasharray": [3, 2],
      "line-opacity": 0.85
    }
  });

  // --- C. Rivers Line ---
  map.addLayer({
    id: "layer-rivers-line",
    type: "line",
    source: "ner_pmtiles",
    "source-layer": "rivers",
    paint: {
      "line-color": "#0284C7",
      "line-width": [
        "interpolate", ["linear"], ["zoom"],
        5, 0.75,
        10, 2.0,
        14, 4.0
      ],
      "line-opacity": 0.9
    }
  });

  // --- D. Roads Line ---
  map.addLayer({
    id: "layer-roads-line",
    type: "line",
    source: "ner_pmtiles",
    "source-layer": "roads",
    minzoom: 5.8,
    paint: {
      "line-color": [
        "match", ["get", "road_type"],
        ["motorway", "trunk"], "#EA580C",
        "primary", "#F59E0B",
        "secondary", "#EAB308",
        "#94A3B8"
      ],
      "line-width": [
        "interpolate", ["linear"], ["zoom"],
        6, 1.0,
        9, 2.0,
        13, 4.0
      ],
      "line-opacity": 0.92
    }
  });

  // --- E. Settlements Circle ---
  map.addLayer({
    id: "layer-settlements-circle",
    type: "circle",
    source: "ner_pmtiles",
    "source-layer": "settlements",
    minzoom: 5.8,
    paint: {
      "circle-color": [
        "match", ["get", "settlement_type"],
        "city", "#DC2626",
        "town", "#EA580C",
        "#10B981"
      ],
      "circle-radius": [
        "interpolate", ["linear"], ["zoom"],
        6, ["match", ["get", "settlement_type"], "city", 4.5, "town", 3.0, 1.5],
        11, ["match", ["get", "settlement_type"], "city", 8.0, "town", 5.5, 3.5]
      ],
      "circle-stroke-color": "#FFFFFF",
      "circle-stroke-width": 1.2,
      "circle-opacity": 0.95
    }
  });

  // Interactive Click Handlers
  setupFeatureInteractivity();
}

// 4. Feature Click & Hover Interactivity
function setupFeatureInteractivity() {
  const interactiveLayers = [
    { id: "layer-settlements-circle", type: "Settlement", titleProp: "name" },
    { id: "layer-roads-line", type: "Road", titleProp: "name" },
    { id: "layer-rivers-line", type: "River", titleProp: "name" },
    { id: "layer-districts-line", type: "District", titleProp: "district_name" },
    { id: "layer-states-fill", type: "State", titleProp: "state_name" }
  ];

  interactiveLayers.forEach(({ id, type, titleProp }) => {
    // Cursor style
    map.on("mouseenter", id, () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", id, () => { map.getCanvas().style.cursor = ""; });

    // Click inspection
    map.on("click", id, (e) => {
      if (!e.features || !e.features.length) return;
      const feat = e.features[0];
      const props = feat.properties;
      const title = props[titleProp] || `Unnamed ${type}`;

      // Open Map Popup
      new maplibregl.Popup({ offset: 10, closeButton: true })
        .setLngLat(e.lngLat)
        .setHTML(`
          <div style="font-size: 13px; line-height: 1.5;">
            <div style="font-size: 10px; font-weight: 700; color: #38BDF8; text-transform: uppercase;">${type}</div>
            <strong style="font-size: 15px; color: #FFF;">${title}</strong>
            ${props.state_name ? `<div style="color: #94A3B8; font-size: 11px;">State: ${props.state_name}</div>` : ""}
            ${props.settlement_type ? `<div style="color: #CBD5E1; font-size: 11px;">Category: ${props.settlement_type}</div>` : ""}
            ${props.road_type ? `<div style="color: #CBD5E1; font-size: 11px;">Class: ${props.road_type} (${props.ref || "No Ref"})</div>` : ""}
            ${props.waterway ? `<div style="color: #CBD5E1; font-size: 11px;">Waterway: ${props.waterway}</div>` : ""}
          </div>
        `)
        .addTo(map);

      // Populate Inspector Tab
      showInspectorDetails(type, title, props);
    });
  });
}

function showInspectorDetails(type, title, props) {
  document.getElementById("inspectorPrompt").style.display = "none";
  const details = document.getElementById("inspectorDetails");
  details.style.display = "block";

  document.getElementById("featTypeBadge").textContent = type;
  document.getElementById("featTitle").textContent = title;

  const table = document.getElementById("featPropsTable");
  table.innerHTML = "";

  Object.entries(props).forEach(([k, v]) => {
    if (v === null || v === undefined || v === "") return;
    const row = document.createElement("div");
    row.className = "prop-row";
    row.innerHTML = `<span class="prop-key">${k}</span><span class="prop-val" title="${v}">${v}</span>`;
    table.appendChild(row);
  });

  // Switch to inspector tab
  switchTab("inspectorTab");
}

// 5. UI Event Listeners (Toggles, Sliders, Quick-Nav)
function setupEventListeners() {
  // Tab Switching
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      switchTab(tabId);
    });
  });

  // Toggle Sidebar
  document.getElementById("btnTogglePanel").addEventListener("click", () => {
    document.getElementById("sidebarPanel").classList.toggle("collapsed");
  });

  // Fit All NER
  document.getElementById("btnFitAll").addEventListener("click", () => {
    flyToState("ALL");
  });

  // State Quick-Nav Pills
  document.querySelectorAll(".nav-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".nav-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      const state = pill.getAttribute("data-state");
      flyToState(state);
    });
  });

  // Basemap Switcher
  document.querySelectorAll(".basemap-card").forEach((card) => {
    card.addEventListener("click", () => {
      document.querySelectorAll(".basemap-card").forEach((c) => c.classList.remove("active"));
      card.classList.add("active");
      const base = card.getAttribute("data-base");
      switchBasemap(base);
    });
  });

  // Raster Toggles & Opacity
  setupLayerToggle("chkHillshade", ["layer-terrain-relief"]);
  setupLayerToggle("chkSlope", ["layer-terrain-slope"]);

  document.getElementById("rngHillshade").addEventListener("input", (e) => {
    const val = e.target.value;
    document.getElementById("valHillshade").textContent = `${val}%`;
    if (map.getLayer("layer-terrain-relief")) {
      map.setPaintProperty("layer-terrain-relief", "raster-opacity", val / 100);
    }
  });

  document.getElementById("rngSlope").addEventListener("input", (e) => {
    const val = e.target.value;
    document.getElementById("valSlope").textContent = `${val}%`;
    if (map.getLayer("layer-terrain-slope")) {
      map.setPaintProperty("layer-terrain-slope", "raster-opacity", val / 100);
    }
  });

  // Vector Layer Toggles
  setupLayerToggle("chkStates", ["layer-states-fill", "layer-states-line"]);
  setupLayerToggle("chkDistricts", ["layer-districts-line"]);
  setupLayerToggle("chkRoads", ["layer-roads-line"]);
  setupLayerToggle("chkRivers", ["layer-rivers-line"]);
  setupLayerToggle("chkSettlements", ["layer-settlements-circle"]);

  // Legend Collapse
  document.getElementById("btnToggleLegend").addEventListener("click", () => {
    const body = document.getElementById("legendBody");
    const chev = document.getElementById("legendChevron");
    body.classList.toggle("hidden");
    chev.classList.toggle("fa-chevron-up");
    chev.classList.toggle("fa-chevron-down");
  });
}

function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".panel-content").forEach((c) => c.classList.remove("active"));

  const targetBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
  const targetContent = document.getElementById(tabId);
  if (targetBtn) targetBtn.classList.add("active");
  if (targetContent) targetContent.classList.add("active");
}

function setupLayerToggle(checkboxId, layerIds) {
  const chk = document.getElementById(checkboxId);
  if (!chk) return;
  chk.addEventListener("change", () => {
    const vis = chk.checked ? "visible" : "none";
    layerIds.forEach((id) => {
      if (map.getLayer(id)) {
        map.setLayoutProperty(id, "visibility", vis);
      }
    });
  });
}

function flyToState(stateKey) {
  const bbox = STATE_BOUNDS[stateKey] || NER_BOUNDS;
  map.fitBounds(bbox, {
    padding: { top: 90, bottom: 40, left: 390, right: 50 },
    duration: 1600,
    essential: true
  });
}

function switchBasemap(baseKey) {
  currentBasemap = baseKey;
  ["osm", "dark", "satellite", "topo"].forEach((k) => {
    if (map.getLayer(`base-${k}`)) {
      map.setLayoutProperty(`base-${k}`, "visibility", k === baseKey ? "visible" : "none");
    }
  });
}

// Start Map on Window Load
window.addEventListener("DOMContentLoaded", initMap);
