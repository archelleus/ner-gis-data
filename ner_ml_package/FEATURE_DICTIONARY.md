# NER Machine Learning Feature Dictionary

This document details the topographic, infrastructural, demographic, and administrative features extracted across the 8 states of the North Eastern Region of India (NER). All proximity queries and distances are computed in metric Cartesian space using **UTM Zone 46N (EPSG:32646)**.

---

## 1. Settlement Feature Table (`ner_settlement_ml_features.parquet` & `.csv`)

- **Rows**: 5,918 settlements (cities, towns, and villages across all 8 NER states)
- **Primary Keys**: `settlement_id`, `name`, `latitude`, `longitude`
- **Recommended Tasks**: Vulnerability assessment, critical infrastructure exposure modeling, population-at-risk ranking, localized landslide risk scoring.

| Feature Name | Type | Units / Format | Range | Physical Meaning & ML Significance |
| :--- | :--- | :--- | :--- | :--- |
| `settlement_id` | Integer | ID | 1 – 5,918 | Unique identifier for each settlement point. |
| `name` | String | UTF-8 Text | — | Settlement place name. |
| `settlement_type` | Categorical | String | `city`, `town`, `village` | Urban hierarchy tier. Determines built-up density and exposure weighting in impact models. |
| `population` | Float / Null | Persons | 10 – 1,116,267 | Census/OSM recorded population. Can be log-transformed (`log1p(population)`) for casualty risk estimation. |
| `state_name` | Categorical | String | 8 states | State administrative boundary. Crucial for high-level spatial splitting. |
| `district_name` | Categorical | String | 119 districts | District administrative boundary. Recommended grouping variable for **Spatial Group-K-Fold Cross-Validation** to prevent spatial data leakage. |
| `latitude` | Float | Decimal Degrees (WGS84) | 21.9°N – 29.3°N | Geodetic latitude (5 decimal places precision ≈ 1.1m). |
| `longitude` | Float | Decimal Degrees (WGS84) | 89.8°E – 97.4°E | Geodetic longitude (5 decimal places precision ≈ 1.1m). |
| `elevation_m` | Float | Meters above sea level | 12.0m – 3,745.0m | Continuous terrain altitude sampled from 30m Copernicus GLO-30 DEM. Influences precipitation patterns, freezing-thawing cycles, and vegetation zones. |
| `slope_deg` | Float | Degrees (0° – 90°) | 0.0° – 63.6° | Local terrain gradient at settlement coordinates. Steep slopes (>30°) are primary physical drivers of shear failure. |
| `slope_class` | Categorical | String | 5 ordinal classes | Ordinal categorization: `Flat (<5°)`, `Gentle (5°-15°)`, `Moderate (15°-30°)`, `Steep (30°-45°)`, `Very Steep (>45°)`. Ready for one-hot encoding or ordinal mapping. |
| `aspect_deg` | Float | Degrees (0° – 360°) | 0.0° – 360.0° | Compass direction facing of the slope calculated using 3×3 Horn's finite-difference method on the 30m DEM. |
| `aspect_direction` | Categorical | String | 8 compass points | Directional binning: `N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW`, `Flat / None`. Directly correlates with monsoon moisture exposure (south/southwest faces receive extreme orographic monsoon precipitation). |
| `dist_to_road_m` | Float | Meters | 0.0m – 37,842.0m | Exact Euclidean metric distance to nearest classified road network. Proximity to road cuts is an anthropogenic landslide trigger (toe cutting, slope destabilization). |
| `nearest_road_type` | Categorical | String | OSM road hierarchy | Functional classification: `motorway`, `trunk`, `primary`, `secondary`, `tertiary`, `unclassified`, `residential`. |
| `nearest_road_ref` | String / Null | Highway Code | e.g., `NH2`, `NH102` | Designated national or state highway designation. |
| `nearest_road_name` | String / Null | UTF-8 Text | Road name | Local naming attribute where mapped. |
| `dist_to_river_m` | Float | Meters | 0.0m – 22,419.0m | Exact Euclidean metric distance to nearest major river channel or perennial waterway. Measures vulnerability to riverine toe erosion and flood undermining. |
| `nearest_river_name` | String / Null | UTF-8 Text | River name | Name of nearest river body (e.g., Brahmaputra, Barak, Teesta, Subansiri). |
| `nearest_waterway_type` | Categorical | String | `river`, `stream`, `canal` | Hydrological waterway class. |

---

## 2. Regional Spatial Inference Grid (`ner_regional_grid_features.parquet` & `_sample_10k.csv`)

- **Rows**: 50,000 systematically sampled terrain coordinates across all land areas of the 8 NER states
- **File Size**: 2.39 MB (Parquet), 0.98 MB (10k CSV sample)
- **Primary Use**: Spatial risk surface evaluation, region-wide inference, generating continuous landslide susceptibility rasters/heatmaps, background (pseudo-absence) sampling for presence-only landslide models (e.g., MaxEnt, One-Class SVM).

| Feature Name | Type | Units / Format | Range | Physical Meaning & ML Significance |
| :--- | :--- | :--- | :--- | :--- |
| `point_id` | Integer | ID | 1 – 50,000 | Unique sequence identifier for each sampled point. |
| `latitude` | Float | Decimal Degrees (WGS84) | 21.9°N – 29.3°N | Geodetic latitude. |
| `longitude` | Float | Decimal Degrees (WGS84) | 89.8°E – 97.4°E | Geodetic longitude. |
| `state_name` | Categorical | String | 8 states | State containing the point. |
| `district_name` | Categorical | String | 119 districts | District containing the point. |
| `elevation_m` | Float | Meters above sea level | 10.0m – 6,028.0m | Regional elevation profile (covers sea-level floodplains to high Himalayan alpine zones). |
| `slope_deg` | Float | Degrees | 0.0° – 69.8° | Continuous terrain slope. Enables high-resolution hazard segmentation. |
| `slope_class` | Categorical | String | 5 ordinal classes | Ordinal slope categorization (`Flat`, `Gentle`, `Moderate`, `Steep`, `Very Steep`). |
| `aspect_deg` | Float | Degrees (0° – 360°) | 0.0° – 360.0° | Horn's method slope orientation. |
| `aspect_direction` | Categorical | String | 8 compass points | Monsoon-relative exposure direction. |
| `dist_to_road_m` | Float | Meters | 0.0m – 48,120.0m | Distance to infrastructure corridor. |
| `dist_to_river_m` | Float | Meters | 0.0m – 24,930.0m | Distance to drainage network. |
| `dist_to_settlement_m` | Float | Meters | 0.0m – 42,650.0m | Distance to nearest human settlement. Used in exposure and accessibility penalty functions. |

---

## 3. District Aggregated Features (`ner_district_ml_features.csv`)

- **Rows**: 119 administrative districts across all 8 NER states
- **Primary Keys**: `district_name`, `state_name`
- **Recommended Tasks**: Macro-level risk prioritization, emergency resource pre-allocation, district vulnerability ranking, tabular regression.

| Feature Name | Type | Units | Physical Meaning & Macro Modeling Role |
| :--- | :--- | :--- | :--- |
| `district_name` | String | Text | Official district name. |
| `state_name` | String | Text | State administrative unit. |
| `area_km2` | Float | km² | Total district land surface area calculated in UTM 46N metric projection. |
| `settlement_count` | Integer | Count | Total recorded human settlements within the district boundaries. |
| `total_settlement_population` | Integer | Persons | Aggregate population summed across known settlement centroids. |
| `elevation_mean_m` | Float | Meters | Mean elevation of settlements within the district. |
| `elevation_min_m` | Float | Meters | Minimum settlement elevation. |
| `elevation_max_m` | Float | Meters | Maximum settlement elevation. High span indicates rugged mountain relief. |
| `slope_mean_deg` | Float | Degrees | Average slope across settlement locations. Indicator of general district topography. |
| `slope_max_deg` | Float | Degrees | Steepest settlement slope in the district. |
| `settlements_pct_steep_slope` | Float | Percentage (%) | Percentage of settlements located on steep slopes (≥ 30°). Direct indicator of high-vulnerability communities. |
| `total_road_length_km` | Float | Kilometers | Total network length of classified highways and arterial roads within the district. |
| `road_density_km_per_km2` | Float | km / km² | Road density metric: `total_road_length_km / area_km2`. Measures anthropogenic modification of hillslopes. |
| `total_river_length_km` | Float | Kilometers | Total length of mapped river channels and drainage lines inside the district. |
| `drainage_density_km_per_km2` | Float | km / km² | Drainage density metric: `total_river_length_km / area_km2`. Key hydrological parameter; high drainage density indicates rapid surface runoff and high dissecting erosion. |

---

## Spatial Cross-Validation Guidance for ML Engineers

1. **Avoid Random Train/Test Splits**: Geographic points exhibit strong spatial autocorrelation (Tobler's First Law of Geography). Random k-fold splitting produces optimistic, overfitted validation scores due to spatial leakage between adjacent points.
2. **Use Spatial Group K-Fold**: Use `district_name` or `state_name` as the group cluster in `sklearn.model_selection.GroupKFold`. This ensures the model is trained on a set of districts and evaluated on entirely unseen geographic districts, proving true generalization.
3. **Presence-Absence Sampling**: For landslide classification models, pair verified landslide inventory points (positive class = 1) with pseudo-absence points sampled from `ner_regional_grid_features.parquet` (negative class = 0, constrained to slope < 10° or buffer > 500m from known slides).
