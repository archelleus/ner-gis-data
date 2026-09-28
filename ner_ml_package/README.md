# North Eastern Region (NER) ML Feature Datasets

This package contains machine learning feature tables, regional spatial evaluation grids, and a feature extraction utility derived from the 8 states of the North Eastern Region of India (Arunachal Pradesh, Assam, Manipur, Meghalaya, Mizoram, Nagaland, Sikkim, and Tripura).

All datasets are pre-processed, clean, tabular structures (`.parquet` and `.csv`) ready for machine learning pipelines (XGBoost, LightGBM, Random Forest, PyTorch, Scikit-Learn) without requiring GIS software or raw GeoTIFF handling.

---

## Package Manifest

| File Name | Format | Size | Rows × Columns | Description |
| :--- | :--- | :--- | :--- | :--- |
| `ner_settlement_ml_features.parquet` | Apache Parquet (Snappy) | 362 KB | 5,918 × 20 | High-performance binary settlement feature table. |
| `ner_settlement_ml_features.csv` | Standard CSV | 828 KB | 5,918 × 20 | Text-formatted settlement feature table. |
| `ner_district_ml_features.csv` | Standard CSV | 11 KB | 119 × 15 | District-level morphological, road, and drainage density aggregations. |
| `ner_regional_grid_features.parquet` | Apache Parquet (Snappy) | 2.39 MB | 50,000 × 13 | Region-wide spatial inference grid sampled uniformly across land bounds. |
| `ner_regional_grid_sample_10k.csv` | Standard CSV | 0.98 MB | 10,000 × 13 | 10k human-readable sample of the regional inference grid. |
| `extract_features_for_points.py` | Python Script | 6.5 KB | — | Standalone feature extractor to enrich custom coordinates or landslide inventories with these identical feature columns. |
| `FEATURE_DICTIONARY.md` | Markdown | 6 KB | — | Field-by-field specifications, physical units, valid ranges, and domain context. |

---

## Data Specifications & Coordinate Systems

- **Input Spatial Reference**: WGS 84 (`EPSG:4326`) for geographic latitude and longitude coordinates.
- **Metric Distance Space**: Euclidean distances (`dist_to_road_m`, `dist_to_river_m`, `dist_to_settlement_m`, densities) were calculated under **UTM Zone 46N (`EPSG:32646`)**, ensuring metric accuracy across the entire North Eastern territory without spherical degree distortion.
- **Topographic Sampling**:
  - `elevation_m` is extracted from 30m resolution Copernicus GLO-30 DEM.
  - `slope_deg` and `slope_class` are derived from the 30m elevation gradient.
  - `aspect_deg` and `aspect_direction` are computed using 3×3 finite-difference gradient estimation (Horn's algorithm).
- **Proximity & Infrastructure**:
  - Road networks: 13,052 vector highway segments interpolated at 50m intervals.
  - River channels: 4,155 perennial waterways and river trunks interpolated at 50m intervals.
  - Settlement network: 5,918 urban and rural centroid coordinates.

---

## Machine Learning Applications

### 1. Landslide Susceptibility & Hazard Classification
- **Feature Set**: `elevation_m`, `slope_deg`, `slope_class`, `aspect_deg`, `aspect_direction`, `dist_to_road_m`, `dist_to_river_m`.
- **Target Formulation**: Binary classification (1 = Landslide Occurrence, 0 = Stable Slope).
- **Absence Sampling**: Negative non-landslide samples can be drawn directly from `ner_regional_grid_features.parquet` (filtered by gentle slope `< 10°` or buffered away from known slide locations).

### 2. Spatial Cross-Validation to Prevent Leakage
- Due to spatial autocorrelation among neighboring geographic coordinates, standard random cross-validation yields inflated accuracy metrics.
- Grouping splits by `district_name` or `state_name` provides true out-of-region generalization benchmarks.

### 3. Continuous Risk Surface Inference
- Once a model is trained, pass `ner_regional_grid_features.parquet` through the model pipeline to generate a continuous susceptibility probability map across all 8 states.

### 4. Settlement Vulnerability & Exposure Ranking
- Combine predicted landslide hazard probability at settlement coordinates with `population`, `settlement_type`, `dist_to_road_m` (isolation penalty), and `settlements_pct_steep_slope` to produce socio-economic risk rankings for disaster mitigation teams.
