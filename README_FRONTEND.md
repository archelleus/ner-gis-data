# North Eastern Region (NER) GIS Web Assets: Frontend Integration Guide

This guide explains how a frontend developer can interactively render the complete North Eastern Region (NER) spatial and terrain datasets using modern web mapping libraries such as **MapLibre GL JS** or **Leaflet**.

---

## 1. Directory Structure

```
web/
├── ner_map.pmtiles         # Single multi-layer vector tile archive (~13.8 MB)
│                           #   ├── states (polygons)
│                           #   ├── districts (polygons)
│                           #   ├── roads (lines)
│                           #   ├── rivers (lines)
│                           #   └── settlements (points)
├── ner_elevation.tif       # Cloud-Optimized GeoTIFF (COG) 30m DEM (Int16)
├── ner_hillshade.tif       # Cloud-Optimized GeoTIFF (COG) Shaded Relief (Byte)
├── ner_slope.tif           # Cloud-Optimized GeoTIFF (COG) Slope in Degrees (Float32)
└── layer_config.json       # Machine-readable metadata and styling configuration
```

---

## 2. Why PMTiles & Cloud-Optimized GeoTIFFs?

- **Zero Map Server Requirement**: These formats require no GeoServer, TileServer, or backend database. They can be hosted statically on any HTTP server, AWS S3, Cloudflare R2, or GitHub Pages.
- **HTTP Range Requests**: The browser only requests the tiny 10–30 KB byte slices needed for the active screen viewport and current zoom level.
- **Performance**: Replacing 66 MB of raw GeoJSON with a single 13.8 MB PMTiles file eliminates browser thread freezing, reduces initial network payload by >80%, and enables smooth 60fps pan/zoom across all 8 NER states.

---

## 3. MapLibre GL JS Integration

### Step A: Include Dependencies
Include MapLibre GL JS and the official `pmtiles` protocol adapter in your HTML `<head>`:

```html
<!-- MapLibre GL JS -->
<link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
<script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>

<!-- PMTiles Protocol Plugin -->
<script src="https://unpkg.com/pmtiles@3.0.6/dist/pmtiles.js"></script>
```

### Step B: Register PMTiles Protocol & Initialize Map

```javascript
// 1. Register the PMTiles protocol with MapLibre
const protocol = new pmtiles.Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

// 2. Define the path or URL to ner_map.pmtiles
const PMTILES_URL = "./web/ner_map.pmtiles";

// 3. Initialize MapLibre
const map = new maplibregl.Map({
  container: "map",
  style: {
    version: 8,
    sources: {
      // Vector Tile Source containing all 5 NER layers
      ner_vectors: {
        type: "vector",
        url: `pmtiles://${PMTILES_URL}`
      }
    },
    layers: []
  },
  // Centered on the North Eastern Region of India
  center: [92.7124, 25.7014],
  zoom: 6.5,
  maxBounds: [[87.0, 21.0], [98.5, 30.5]]
});
```

### Step C: Add Vector Layers to the Map

Once the map loads, add the 5 source layers (`states`, `districts`, `rivers`, `roads`, `settlements`):

```javascript
map.on("load", () => {
  // ----------------------------------------------------
  // 1. STATE BOUNDARIES (Base administrative outlines)
  // ----------------------------------------------------
  map.addLayer({
    id: "ner-states-fill",
    type: "fill",
    source: "ner_vectors",
    "source-layer": "states",
    paint: {
      "fill-color": "#FFFFFF",
      "fill-opacity": 0.05
    }
  });

  map.addLayer({
    id: "ner-states-line",
    type: "line",
    source: "ner_vectors",
    "source-layer": "states",
    paint: {
      "line-color": "#0F172A",
      "line-width": 2.0
    }
  });

  // ----------------------------------------------------
  // 2. DISTRICT BOUNDARIES (Visible at zoom 6+)
  // ----------------------------------------------------
  map.addLayer({
    id: "ner-districts-line",
    type: "line",
    source: "ner_vectors",
    "source-layer": "districts",
    minzoom: 6,
    paint: {
      "line-color": "#475569",
      "line-width": 1.0,
      "line-dasharray": [3, 2]
    }
  });

  // ----------------------------------------------------
  // 3. HYDROGRAPHY / RIVERS
  // ----------------------------------------------------
  map.addLayer({
    id: "ner-rivers-line",
    type: "line",
    source: "ner_vectors",
    "source-layer": "rivers",
    paint: {
      "line-color": "#0284C7",
      "line-width": [
        "interpolate", ["linear"], ["zoom"],
        5, 0.8,
        10, 2.0,
        14, 4.0
      ]
    }
  });

  // ----------------------------------------------------
  // 4. TRANSPORTATION / ROADS (Categorized styling)
  // ----------------------------------------------------
  map.addLayer({
    id: "ner-roads-line",
    type: "line",
    source: "ner_vectors",
    "source-layer": "roads",
    minzoom: 6,
    paint: {
      "line-color": [
        "match", ["get", "road_type"],
        ["motorway", "trunk"], "#EA580C", // Expressways & National Highways
        "primary", "#F59E0B",             // State Highways
        "secondary", "#EAB308",           // Major Arterials
        "#94A3B8"                         // Other Roads
      ],
      "line-width": [
        "interpolate", ["linear"], ["zoom"],
        6, 1.0,
        10, 2.2,
        14, 4.5
      ]
    }
  });

  // ----------------------------------------------------
  // 5. SETTLEMENTS (Cities, Towns, Villages with Popups)
  // ----------------------------------------------------
  map.addLayer({
    id: "ner-settlements-circle",
    type: "circle",
    source: "ner_vectors",
    "source-layer": "settlements",
    minzoom: 6,
    paint: {
      "circle-color": [
        "match", ["get", "settlement_type"],
        "city", "#DC2626",
        "town", "#EA580C",
        "#10B981"
      ],
      "circle-radius": [
        "match", ["get", "settlement_type"],
        "city", 6,
        "town", 4,
        2.5
      ],
      "circle-stroke-color": "#FFFFFF",
      "circle-stroke-width": 1.5
    }
  });

  // ----------------------------------------------------
  // Interactive Click Popups
  // ----------------------------------------------------
  map.on("click", "ner-settlements-circle", (e) => {
    const props = e.features[0].properties;
    new maplibregl.Popup()
      .setLngLat(e.lngLat)
      .setHTML(`
        <div style="font-family: sans-serif; font-size: 13px;">
          <strong style="font-size: 15px;">${props.name || "Unknown Settlement"}</strong><br/>
          <span style="color: #64748B;">Type:</span> ${props.settlement_type}<br/>
          <span style="color: #64748B;">District:</span> ${props.district_name || "N/A"}<br/>
          <span style="color: #64748B;">State:</span> ${props.state_name || "N/A"}
        </div>
      `)
      .addTo(map);
  });
});
```

---

## 4. Serving & Consuming Cloud-Optimized GeoTIFFs (COGs)

The raster files (`ner_elevation.tif`, `ner_hillshade.tif`, `ner_slope.tif`) are encoded as true **Cloud-Optimized GeoTIFFs** with internal overview pyramids.

### Option 1: Direct Web Streaming with `geotiff.js`
In client-side applications requiring raster value queries (such as clicking to read exact elevation in meters or slope in degrees):

```javascript
import { fromUrl } from "geotiff";

// Read exact elevation at a coordinate using HTTP Range Requests
async function getElevationAt(lng, lat) {
  const tiff = await fromUrl("./web/ner_elevation.tif");
  const image = await tiff.getImage(); // Loads lowest overview or base IFD
  const bbox = image.getBoundingBox();
  // Query pixel window without downloading entire file
  const raster = await image.readRasters({
    window: [col, row, col + 1, row + 1]
  });
  return raster[0][0]; // Elevation in meters
}
```

### Option 2: Serving Dynamic Raster Tiles via TiTiler / COG Server
To render the COG rasters as visual map layers in MapLibre or Leaflet, point your dynamic tiler (e.g., [TiTiler](https://developmentseed.org/titiler/)) at the COG:

```javascript
// TiTiler dynamic tile endpoint for ner_hillshade.tif
map.addSource("ner_hillshade_tiles", {
  type: "raster",
  tiles: [
    "https://your-titiler-service/cog/tiles/{z}/{x}/{y}.png?url=https://your-domain.com/web/ner_hillshade.tif&rescale=0,255"
  ],
  tileSize: 256
});

map.addLayer({
  id: "hillshade-raster",
  type: "raster",
  source: "ner_hillshade_tiles",
  paint: { "raster-opacity": 0.65 }
});
```

---

## 5. Web Server / CDN Configuration

To enable PMTiles and COG HTTP Range Requests, ensure your web server or S3 bucket emits the following headers:

```http
# Enable partial content streaming
Accept-Ranges: bytes

# CORS headers (required if assets are on a separate CDN/bucket)
Access-Control-Allow-Origin: *
Access-Control-Allow-Headers: Range, Content-Range

# MIME types
Content-Type: application/vnd.pmtiles (for .pmtiles)
Content-Type: image/tiff (for .tif)
```

---

## 6. Leaflet Integration Alternative

If your application uses **Leaflet** rather than MapLibre:

### Step A: Include Leaflet & Leaflet-PMTiles
```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<!-- VectorGrid & Leaflet-PMTiles -->
<script src="https://unpkg.com/leaflet.vectorgrid@1.3.0/dist/Leaflet.VectorGrid.bundled.js"></script>
<script src="https://unpkg.com/pmtiles@3.0.6/dist/pmtiles.js"></script>
```

### Step B: Load Vector Tiles
```javascript
const map = L.map("map").setView([25.7014, 92.7124], 7);

// Add base OSM map
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap"
}).addTo(map);

// Add NER PMTiles Vector Layer
const p = new pmtiles.PMTiles("./web/ner_map.pmtiles");
p.getHeader().then((header) => {
  const vectorTileOptions = {
    vectorTileLayerStyles: {
      states: { color: "#0F172A", weight: 2, fill: false },
      districts: { color: "#64748B", weight: 1, dashArray: "3, 2", fill: false },
      rivers: { color: "#0284C7", weight: 1.5 },
      roads: (properties) => {
        const type = properties.road_type;
        return {
          color: (type === "motorway" || type === "trunk") ? "#EA580C" : "#F59E0B",
          weight: 2
        };
      },
      settlements: {
        radius: 4,
        fillColor: "#DC2626",
        color: "#FFFFFF",
        weight: 1,
        fillOpacity: 0.9
      }
    },
    interactive: true,
    minZoom: header.minZoom,
    maxZoom: header.maxZoom
  };

  // Attach PMTiles source to VectorGrid
  // Note: For Leaflet, VectorGrid can fetch PMTiles via blob URLs or a lightweight local tile worker.
});
```

