# North Eastern Region (NER) GIS Project: Master Data Dictionary

## 1. Project Overview & Spatial Reference

The North Eastern Region (NER) GIS repository provides authoritative, validated, and web-optimized geospatial layers covering all 8 states: **Arunachal Pradesh, Assam, Manipur, Meghalaya, Mizoram, Nagaland, Sikkim, and Tripura**.

- **Coordinate Reference System (CRS)**: `EPSG:4326` (WGS 84, Lat/Lon)
- **Bounding Box**: `[88.013472°E, 21.941250°N, 97.411250°E, 29.461528°N]`
- **Target Audience**: GIS analysts, Web frontend developers (MapLibre / Leaflet), and Machine Learning pipelines.

---

## 2. Layer Catalog & Summary

| Layer Identifier | File Type / Location | Source Dataset | Resolution / Scale | Features / Cells | Purpose |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **`states`** | Vector GeoJSON & PMTiles | geoBoundaries ADM1 | 1:50,000 | 8 polygons | Primary administrative demarcation |
| **`districts`** | Vector GeoJSON & PMTiles | geoBoundaries ADM2 | 1:50,000 | 119 polygons | District-level territorial aggregation |
| **`roads`** | Vector GeoJSON & PMTiles | OpenStreetMap (OSM) | Street-level | 13,052 segments | Transport corridor accessibility |
| **`rivers`** | Vector GeoJSON & PMTiles | OpenStreetMap (OSM) | Basin-level | 4,155 segments | Drainage network & flood plains |
| **`settlements`** | Vector GeoJSON & PMTiles | OpenStreetMap (OSM) | Point locations | 5,918 nodes | Population exposure & human activity |
| **`ner_elevation`** | GeoTIFF & COG (Int16) | SRTM Skadi (NASA/USGS)| 1 arc-sec (~30 m) | 915,933,736 cells | Topographic elevation & base DEM |
| **`ner_hillshade`** | GeoTIFF & COG (Byte) | Derived from DEM | 1 arc-sec (~30 m) | 915,933,736 cells | 3D terrain visualization & relief |
| **`ner_slope`** | GeoTIFF & COG (Float32)| Derived from DEM | 1 arc-sec (~30 m) | 915,933,736 cells | Terrain incline & ML susceptibility |

---

## 3. Vector Layer Specifications

### 3.1 States (`data/processed/ner_states.geojson` & `web/ner_map.pmtiles` layer `states`)
- **Geometry**: `MultiPolygon` / `Polygon`
- **Total Features**: `8`
- **Source**: geoBoundaries v6 Open ADM1 (India)

| Field Name | Type | Description | Example Values |
| :--- | :--- | :--- | :--- |
| `state_name` | String | Standardized English name of the state | `"Assam"`, `"Sikkim"`, `"Meghalaya"` |
| `shapeID` | String | Unique geoBoundaries identifier | `"IND-ADM1-3_0_0-B1"` |
| `shapeISO` | String | ISO 3166-2 state code | `"IN-AS"`, `"IN-SK"`, `"IN-ML"` |

### 3.2 Districts (`data/processed/ner_districts.geojson` & `web/ner_map.pmtiles` layer `districts`)
- **Geometry**: `MultiPolygon` / `Polygon`
- **Total Features**: `119`
- **Source**: geoBoundaries v6 Open ADM2 (India)

| Field Name | Type | Description | Example Values |
| :--- | :--- | :--- | :--- |
| `district_name` | String | Standardized English name of the administrative district | `"Kamrup Metropolitan"`, `"East Khasi Hills"`, `"Aizawl"` |
| `state_name` | String | Parent state name | `"Assam"`, `"Meghalaya"`, `"Mizoram"` |
| `admin_level` | String | Administrative level hierarchy | `"ADM2"` |
| `shapeID` | String | Unique geoBoundaries district identifier | `"IND-ADM2-3_0_0-B102"` |

### 3.3 Roads (`data/processed/ner_roads.geojson` & `web/ner_map.pmtiles` layer `roads`)
- **Geometry**: `LineString` / `MultiLineString`
- **Total Features**: `13,052`
- **Source**: OpenStreetMap (OSM) via Overpass API

| Field Name | Type | Description | Example Values |
| :--- | :--- | :--- | :--- |
| `name` | String | Official or local road name | `"National Highway 27"`, `"GS Road"`, `"AT Road"` |
| `ref` | String | Route reference code | `"NH-27"`, `"NH-10"`, `"SH-1"` |
| `road_type` | String | Functional road classification | `"motorway"`, `"trunk"`, `"primary"`, `"secondary"`, `"tertiary"` |
| `surface` | String | Pavement condition where recorded | `"paved"`, `"asphalt"`, `"unpaved"` |
| `state_name` | String | Parent state traversed by segment | `"Assam"`, `"Nagaland"` |
| `osm_id` | String | Unique OpenStreetMap way identifier | `"123456789"` |

### 3.4 Rivers (`data/processed/ner_rivers.geojson` & `web/ner_map.pmtiles` layer `rivers`)
- **Geometry**: `LineString` / `MultiLineString`
- **Total Features**: `4,155`
- **Source**: OpenStreetMap (OSM) Hydrography

| Field Name | Type | Description | Example Values |
| :--- | :--- | :--- | :--- |
| `name` | String | Name of the river, stream, or channel | `"Brahmaputra"`, `"Barak"`, `"Teesta"`, `"Subansiri"` |
| `waterway` | String | Waterway classification | `"river"`, `"stream"`, `"canal"` |
| `state_name` | String | Parent state through which waterway flows | `"Assam"`, `"Arunachal Pradesh"` |
| `osm_id` | String | Unique OpenStreetMap way identifier | `"987654321"` |

### 3.5 Settlements (`data/processed/ner_settlements.geojson` & `web/ner_map.pmtiles` layer `settlements`)
- **Geometry**: `Point`
- **Total Features**: `5,918`
- **Source**: OpenStreetMap (OSM) Places

| Field Name | Type | Description | Example Values |
| :--- | :--- | :--- | :--- |
| `name` | String | Name of populated place | `"Guwahati"`, `"Shillong"`, `"Imphal"`, `"Agartala"` |
| `settlement_type`| String | Hierarchical tier (`city`, `town`, `village`) | `"city"`, `"town"`, `"village"` |
| `population` | Integer | Resident population where available in OSM | `957352`, `143229` |
| `district_name` | String | Spatially joined district name | `"Kamrup Metropolitan"`, `"East Khasi Hills"` |
| `state_name` | String | Parent state name | `"Assam"`, `"Meghalaya"` |
| `osm_id` | String | Unique OpenStreetMap node identifier | `"345678901"` |

---

## 4. Raster Terrain Layer Specifications

All raster datasets share an identical spatial grid:
- **Dimensions**: `33,832 x 27,073` pixels (**915,933,736** total grid cells)
- **Resolution**: `0.00027778° x 0.00027778°` (~30.8 m at equator, ~27.7 m at 26°N)
- **Bounding Box**: `[88.013472°E, 21.941250°N, 97.411250°E, 29.461528°N]`
- **Alignment**: 100% exact 1-to-1 pixel match across Elevation, Hillshade, and Slope.

### 4.1 Elevation DEM (`terrain/ner_elevation.tif` & `web/ner_elevation.tif`)
- **Data Type**: `Int16` (Signed 16-bit integer)
- **NoData Value**: `-32768.0` (outside NER borders)
- **Value Range**: `-443 m` to `8,375 m` (Kangchenjunga peak)
- **Units**: Meters above mean sea level (EGM96 vertical datum)
- **Source**: SRTM Skadi 1-arc-second tiles (NASA / USGS via AWS Open Data)
- **Web Encoding**: Cloud-Optimized GeoTIFF (COG), 6 overviews (2x to 64x), DEFLATE, `PREDICTOR=2`

### 4.2 Hillshade Relief (`terrain/ner_hillshade.tif` & `web/ner_hillshade.tif`)
- **Data Type**: `Byte` (UInt8, 8-bit unsigned integer)
- **NoData Value**: `0` (outside NER borders)
- **Value Range**: `1` to `255`
- **Parameters**: Solar Azimuth: `315.0°` (North-West), Solar Altitude: `45.0°`, Scale factor: `111,120`
- **Purpose**: High-contrast cartographic texture, 3D surface perception, and shaded background map rendering
- **Web Encoding**: Cloud-Optimized GeoTIFF (COG), 6 overviews, DEFLATE, `PREDICTOR=2`

### 4.3 Terrain Slope (`terrain/ner_slope.tif` & `web/ner_slope.tif`)
- **Data Type**: `Float32` (32-bit floating point)
- **NoData Value**: `-9999.0` (outside NER borders)
- **Value Range**: `0.00°` to `89.13°`
- **Mean Slope**: `16.36°` (Median: `14.54°`)
- **Units**: Degrees Incline ($0^\circ = 	ext{horizontal}$, $90^\circ = 	ext{vertical}$)
- **Purpose**: Physical terrain steepness feature for machine learning, landslide susceptibility models, and watershed analysis
- **Web Encoding**: Cloud-Optimized GeoTIFF (COG), 6 overviews, DEFLATE, `PREDICTOR=3` (IEEE float)

---

## 5. Web Distribution & Frontend Assets

- **Vector Archive**: `web/ner_map.pmtiles` (13.8 MB) — v3 PMTiles containing all 5 vector layers.
- **Raster COGs**: `web/ner_elevation.tif` (290 MB), `web/ner_hillshade.tif` (279 MB), `web/ner_slope.tif` (1.26 GB).
- **Configuration**: `web/layer_config.json` — Machine-readable configuration detailing sources, bounds, zoom thresholds, and styling rules.
- **Integration Manual**: `README_FRONTEND.md` — Copy-pasteable MapLibre GL JS and Leaflet examples.
