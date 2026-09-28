#!/usr/bin/env python3
"""
NER ML Feature Extraction Pipeline
Extracts standardized, ready-to-train machine learning feature tables
from the 30m terrain rasters (elevation, slope) and spatial vector datasets
(roads, rivers, settlements, administrative boundaries).

Outputs generated in ner_ml_package/:
1. ner_settlement_ml_features.csv & .parquet
2. ner_district_ml_features.csv
3. ner_regional_grid_features.parquet & ner_regional_grid_sample_10k.csv
4. extract_features_for_points.py
5. FEATURE_DICTIONARY.md
6. README.md
"""

import os
import time
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from scipy.spatial import cKDTree
from shapely.geometry import Point, MultiLineString, LineString, Polygon, MultiPolygon
from shapely.ops import unary_union

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
TERRAIN_DIR = os.path.join(PROJECT_ROOT, "terrain")
OUT_DIR = os.path.join(PROJECT_ROOT, "ner_ml_package")

STATES_FILE = os.path.join(DATA_DIR, "ner_states.geojson")
DISTRICTS_FILE = os.path.join(DATA_DIR, "ner_districts.geojson")
ROADS_FILE = os.path.join(DATA_DIR, "ner_roads.geojson")
RIVERS_FILE = os.path.join(DATA_DIR, "ner_rivers.geojson")
SETTLEMENTS_FILE = os.path.join(DATA_DIR, "ner_settlements.geojson")

DEM_FILE = os.path.join(TERRAIN_DIR, "ner_elevation.tif")
SLOPE_FILE = os.path.join(TERRAIN_DIR, "ner_slope.tif")

# Projected CRS for metric distance queries (covers entire NER accurately)
METRIC_CRS = "EPSG:32646"  # WGS 84 / UTM zone 46N


def classify_slope(slope_deg):
    """Categorize slope in degrees into standard geomorphic hazard classes."""
    if slope_deg is None or np.isnan(slope_deg) or slope_deg < 0:
        return "Unknown"
    elif slope_deg < 5.0:
        return "Flat (< 5°)"
    elif slope_deg < 15.0:
        return "Gentle (5°-15°)"
    elif slope_deg < 30.0:
        return "Moderate (15°-30°)"
    elif slope_deg < 45.0:
        return "Steep (30°-45°)"
    else:
        return "Precipitous (> 45°)"


def classify_aspect(aspect_deg):
    """Convert aspect degree (0-360) into 8 compass directions."""
    if aspect_deg is None or np.isnan(aspect_deg) or aspect_deg < 0:
        return "Flat / None"
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((aspect_deg + 22.5) % 360 // 45)
    return directions[idx]


def build_line_kdtree(gdf_metric):
    """
    Sample dense points along line geometries (every 50m) and build a cKDTree
    for ultra-fast Euclidean proximity queries.
    Returns: tree, metadata_array
    """
    sample_points = []
    meta_records = []

    for idx, row in gdf_metric.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        lines = [geom] if isinstance(geom, LineString) else list(geom.geoms)

        for line in lines:
            length = line.length
            # Sample points every 50 meters along the line
            num_points = max(2, int(length // 50) + 1)
            distances = np.linspace(0, length, num_points)
            for d in distances:
                pt = line.interpolate(d)
                sample_points.append((pt.x, pt.y))
                meta_records.append(idx)

    pts_array = np.array(sample_points, dtype=np.float64)
    meta_array = np.array(meta_records, dtype=np.int32)
    tree = cKDTree(pts_array)
    return tree, meta_array


def sample_raster_points(raster_path, coords_lon_lat):
    """Sample raster values at given (lon, lat) coordinates."""
    values = []
    with rasterio.open(raster_path) as src:
        nodata = src.nodata
        for val in src.sample(coords_lon_lat):
            v = float(val[0])
            if nodata is not None and (v == nodata or v < -10000):
                values.append(np.nan)
            else:
                values.append(v)
    return np.array(values, dtype=np.float32)


def calculate_local_aspect(dem_src, lons, lats):
    """
    Compute 3x3 finite difference aspect in degrees (0-360)
    for a list of lon/lat points using Horn's method.
    """
    aspects = []
    transform = dem_src.transform
    inv_transform = ~transform

    for lon, lat in zip(lons, lats):
        px, py = inv_transform * (lon, lat)
        col, row = int(round(px)), int(round(py))

        # Check bounds
        if row < 1 or row >= dem_src.height - 1 or col < 1 or col >= dem_src.width - 1:
            aspects.append(np.nan)
            continue

        # Read 3x3 window and cast to float64
        win = dem_src.read(1, window=((row - 1, row + 2), (col - 1, col + 2)))
        if win.shape != (3, 3):
            aspects.append(np.nan)
            continue
        w = win.astype(np.float64)

        # Finite difference gradient (Horn's method)
        # [z1 z2 z3]
        # [z4 z5 z6]
        # [z7 z8 z9]
        z1, z2, z3 = w[0, 0], w[0, 1], w[0, 2]
        z4, z5, z6 = w[1, 0], w[1, 1], w[1, 2]
        z7, z8, z9 = w[2, 0], w[2, 1], w[2, 2]

        dz_dx = ((z3 + 2.0 * z6 + z9) - (z1 + 2.0 * z4 + z7)) / 8.0
        dz_dy = ((z7 + 2.0 * z8 + z9) - (z1 + 2.0 * z2 + z3)) / 8.0

        if dz_dx == 0 and dz_dy == 0:
            aspects.append(0.0)
        else:
            aspect = np.degrees(np.arctan2(-dz_dx, dz_dy))
            if aspect < 0:
                aspect += 360.0
            aspects.append(round(aspect, 1))

    return np.array(aspects, dtype=np.float32)


def main():
    start_time = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 65)
    print("NER MACHINE LEARNING FEATURE EXTRACTION PIPELINE")
    print("=" * 65)

    # 1. Load Vector Datasets
    print("\n[1/5] Loading spatial vector datasets...")
    states_gdf = gpd.read_file(STATES_FILE)
    districts_gdf = gpd.read_file(DISTRICTS_FILE)
    roads_gdf = gpd.read_file(ROADS_FILE)
    rivers_gdf = gpd.read_file(RIVERS_FILE)
    settlements_gdf = gpd.read_file(SETTLEMENTS_FILE)

    print(f"  - States: {len(states_gdf)}")
    print(f"  - Districts: {len(districts_gdf)}")
    print(f"  - Roads: {len(roads_gdf):,}")
    print(f"  - Rivers: {len(rivers_gdf):,}")
    print(f"  - Settlements: {len(settlements_gdf):,}")

    # Project to metric CRS for proximity queries
    print("\n[2/5] Projecting vectors to UTM Zone 46N (EPSG:32646) for metric distance trees...")
    roads_utm = roads_gdf.to_crs(METRIC_CRS)
    rivers_utm = rivers_gdf.to_crs(METRIC_CRS)
    settlements_utm = settlements_gdf.to_crs(METRIC_CRS)

    print("  - Building road proximity KDTree (sampling vertices every 50m)...")
    road_tree, road_meta = build_line_kdtree(roads_utm)
    print("  - Building river proximity KDTree (sampling vertices every 50m)...")
    river_tree, river_meta = build_line_kdtree(rivers_utm)

    # 2. Extract Settlement Feature Dataset
    print("\n[3/5] Extracting settlement risk & vulnerability features (5,918 settlements)...")
    settlement_lons = settlements_gdf.geometry.x.values
    settlement_lats = settlements_gdf.geometry.y.values
    st_lon_lat = list(zip(settlement_lons, settlement_lats))

    # Raster sampling
    print("  - Sampling 30m Elevation DEM...")
    elev_vals = sample_raster_points(DEM_FILE, st_lon_lat)

    print("  - Sampling 30m Terrain Slope...")
    slope_vals = sample_raster_points(SLOPE_FILE, st_lon_lat)

    print("  - Computing local terrain aspect (0°-360°)...")
    with rasterio.open(DEM_FILE) as dem_src:
        aspect_vals = calculate_local_aspect(dem_src, settlement_lons, settlement_lats)

    # Proximity queries
    print("  - Querying distance to nearest road and road type...")
    st_pts_utm = np.c_[settlements_utm.geometry.x.values, settlements_utm.geometry.y.values]
    road_dists, road_indices = road_tree.query(st_pts_utm)
    matched_road_idx = road_meta[road_indices]
    nearest_road_types = roads_gdf.iloc[matched_road_idx]["road_type"].values
    nearest_road_refs = roads_gdf.iloc[matched_road_idx]["ref"].fillna("").values
    nearest_road_names = roads_gdf.iloc[matched_road_idx]["name"].fillna("").values

    print("  - Querying distance to nearest river channel...")
    river_dists, river_indices = river_tree.query(st_pts_utm)
    matched_river_idx = river_meta[river_indices]
    nearest_river_names = rivers_gdf.iloc[matched_river_idx]["name"].fillna("").values
    nearest_waterway_types = rivers_gdf.iloc[matched_river_idx]["waterway"].fillna("river").values

    settlement_df = pd.DataFrame({
        "settlement_id": settlements_gdf.index + 1,
        "name": settlements_gdf["name"],
        "settlement_type": settlements_gdf["settlement_type"],
        "population": settlements_gdf["population"].replace(0, np.nan),
        "state_name": settlements_gdf["state_name"],
        "district_name": settlements_gdf["district_name"],
        "latitude": np.round(settlement_lats, 5),
        "longitude": np.round(settlement_lons, 5),
        "elevation_m": np.round(elev_vals, 1),
        "slope_deg": np.round(slope_vals, 2),
        "slope_class": [classify_slope(s) for s in slope_vals],
        "aspect_deg": np.round(aspect_vals, 1),
        "aspect_direction": [classify_aspect(a) for a in aspect_vals],
        "dist_to_road_m": np.round(road_dists, 1),
        "nearest_road_type": nearest_road_types,
        "nearest_road_ref": nearest_road_refs,
        "nearest_road_name": nearest_road_names,
        "dist_to_river_m": np.round(river_dists, 1),
        "nearest_river_name": nearest_river_names,
        "nearest_waterway_type": nearest_waterway_types
    })

    settlement_csv = os.path.join(OUT_DIR, "ner_settlement_ml_features.csv")
    settlement_parquet = os.path.join(OUT_DIR, "ner_settlement_ml_features.parquet")
    settlement_df.to_csv(settlement_csv, index=False)
    settlement_df.to_parquet(settlement_parquet, index=False)
    print(f"  ✓ Saved settlement features: {settlement_csv} ({os.path.getsize(settlement_csv) / 1024:.1f} KB)")
    print(f"  ✓ Saved settlement parquet:  {settlement_parquet} ({os.path.getsize(settlement_parquet) / 1024:.1f} KB)")

    # 3. Extract District Summary Features
    print("\n[4/5] Extracting district-level summary features (119 districts)...")
    districts_utm = districts_gdf.to_crs(METRIC_CRS)
    district_records = []

    # Pre-read downsampled elevation and slope for zonal statistics
    with rasterio.open(DEM_FILE) as dem_src:
        dem_affine = dem_src.transform
        dem_nodata = dem_src.nodata

    for idx, row in districts_gdf.iterrows():
        d_name = row["district_name"]
        s_name = row["state_name"]
        d_geom = row.geometry
        d_geom_utm = districts_utm.loc[idx].geometry
        area_km2 = d_geom_utm.area / 1e6

        # Roads inside district
        d_roads = roads_utm[roads_utm.intersects(d_geom_utm)]
        road_len_km = d_roads.geometry.intersection(d_geom_utm).length.sum() / 1000.0
        road_density = road_len_km / max(area_km2, 0.1)

        # Rivers inside district
        d_rivers = rivers_utm[rivers_utm.intersects(d_geom_utm)]
        river_len_km = d_rivers.geometry.intersection(d_geom_utm).length.sum() / 1000.0
        river_density = river_len_km / max(area_km2, 0.1)

        # Settlements inside district
        d_st = settlement_df[(settlement_df["district_name"] == d_name) & (settlement_df["state_name"] == s_name)]
        st_count = len(d_st)
        pop_series = pd.to_numeric(d_st["population"], errors="coerce").fillna(0)
        total_pop = int(pop_series.sum())

        # Mean slope and elevation from settlements inside district as fast proxy
        d_elev_mean = float(d_st["elevation_m"].mean()) if len(d_st) and not pd.isna(d_st["elevation_m"].mean()) else None
        d_elev_min = float(d_st["elevation_m"].min()) if len(d_st) and not pd.isna(d_st["elevation_m"].min()) else None
        d_elev_max = float(d_st["elevation_m"].max()) if len(d_st) and not pd.isna(d_st["elevation_m"].max()) else None
        d_slope_mean = float(d_st["slope_deg"].mean()) if len(d_st) and not pd.isna(d_st["slope_deg"].mean()) else None
        d_slope_max = float(d_st["slope_deg"].max()) if len(d_st) and not pd.isna(d_st["slope_deg"].max()) else None
        pct_steep = float((d_st["slope_deg"] >= 30.0).mean() * 100.0) if len(d_st) and not pd.isna(d_st["slope_deg"].mean()) else None

        district_records.append({
            "district_name": d_name,
            "state_name": s_name,
            "area_km2": round(area_km2, 1),
            "settlement_count": st_count,
            "total_settlement_population": total_pop,
            "elevation_mean_m": round(d_elev_mean, 1) if d_elev_mean is not None else None,
            "elevation_min_m": round(d_elev_min, 1) if d_elev_min is not None else None,
            "elevation_max_m": round(d_elev_max, 1) if d_elev_max is not None else None,
            "slope_mean_deg": round(d_slope_mean, 2) if d_slope_mean is not None else None,
            "slope_max_deg": round(d_slope_max, 2) if d_slope_max is not None else None,
            "settlements_pct_steep_slope": round(pct_steep, 1) if pct_steep is not None else None,
            "total_road_length_km": round(road_len_km, 1),
            "road_density_km_per_km2": round(road_density, 3),
            "total_river_length_km": round(river_len_km, 1),
            "drainage_density_km_per_km2": round(river_density, 3),
        })

    district_df = pd.DataFrame(district_records)
    district_df = district_df.sort_values(by=["state_name", "district_name"]).reset_index(drop=True)
    district_csv = os.path.join(OUT_DIR, "ner_district_ml_features.csv")
    district_df.to_csv(district_csv, index=False)
    print(f"  ✓ Saved district features:   {district_csv} ({os.path.getsize(district_csv) / 1024:.1f} KB)")

    # 4. Generate Regional Spatial Inference Grid (50,000 Points)
    print("\n[5/5] Generating regional inference grid (50,000 points across NER bounds)...")
    ner_union = states_gdf.geometry.unary_union
    min_x, min_y, max_x, max_y = ner_union.bounds

    # Generate random points inside the multi-state boundary
    np.random.seed(42)
    grid_points = []
    batch_size = 70000
    target_count = 50000

    while len(grid_points) < target_count:
        rand_lons = np.random.uniform(min_x, max_x, batch_size)
        rand_lats = np.random.uniform(min_y, max_y, batch_size)
        pts_gdf = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy(rand_lons, rand_lats),
            crs="EPSG:4326"
        )
        # Spatial join with districts to get state and district attribution
        joined = gpd.sjoin(pts_gdf, districts_gdf[["district_name", "state_name", "geometry"]], how="inner", predicate="within")
        joined["longitude"] = joined.geometry.x
        joined["latitude"] = joined.geometry.y
        records = joined[["longitude", "latitude", "district_name", "state_name"]].to_dict("records")
        grid_points.extend(records)
        if len(grid_points) >= target_count:
            grid_points = grid_points[:target_count]
            break
        print(f"    Sampled {len(grid_points):,}/{target_count:,} valid land points...")

    grid_df = pd.DataFrame(grid_points)
    grid_lons = grid_df["longitude"].values
    grid_lats = grid_df["latitude"].values
    grid_lon_lat = list(zip(grid_lons, grid_lats))

    print("  - Sampling Elevation & Slope for regional grid...")
    grid_elev = sample_raster_points(DEM_FILE, grid_lon_lat)
    grid_slope = sample_raster_points(SLOPE_FILE, grid_lon_lat)

    with rasterio.open(DEM_FILE) as dem_src:
        grid_aspect = calculate_local_aspect(dem_src, grid_lons, grid_lats)

    print("  - Calculating distances to roads, rivers, and settlements...")
    grid_pts_utm = gpd.GeoSeries(gpd.points_from_xy(grid_lons, grid_lats), crs="EPSG:4326").to_crs(METRIC_CRS)
    grid_coords_utm = np.c_[grid_pts_utm.geometry.x.values, grid_pts_utm.geometry.y.values]

    grid_road_dists, _ = road_tree.query(grid_coords_utm)
    grid_river_dists, _ = river_tree.query(grid_coords_utm)

    # Settlement proximity tree
    st_tree = cKDTree(st_pts_utm)
    grid_st_dists, _ = st_tree.query(grid_coords_utm)

    grid_df["point_id"] = np.arange(1, len(grid_df) + 1)
    grid_df["latitude"] = np.round(grid_lats, 5)
    grid_df["longitude"] = np.round(grid_lons, 5)
    grid_df["elevation_m"] = np.round(grid_elev, 1)
    grid_df["slope_deg"] = np.round(grid_slope, 2)
    grid_df["slope_class"] = [classify_slope(s) for s in grid_slope]
    grid_df["aspect_deg"] = np.round(grid_aspect, 1)
    grid_df["aspect_direction"] = [classify_aspect(a) for a in grid_aspect]
    grid_df["dist_to_road_m"] = np.round(grid_road_dists, 1)
    grid_df["dist_to_river_m"] = np.round(grid_river_dists, 1)
    grid_df["dist_to_settlement_m"] = np.round(grid_st_dists, 1)

    # Reorder columns
    col_order = [
        "point_id", "latitude", "longitude", "state_name", "district_name",
        "elevation_m", "slope_deg", "slope_class", "aspect_deg", "aspect_direction",
        "dist_to_road_m", "dist_to_river_m", "dist_to_settlement_m"
    ]
    grid_df = grid_df[col_order]

    grid_parquet = os.path.join(OUT_DIR, "ner_regional_grid_features.parquet")
    grid_csv_sample = os.path.join(OUT_DIR, "ner_regional_grid_sample_10k.csv")
    grid_df.to_parquet(grid_parquet, index=False)
    grid_df.head(10000).to_csv(grid_csv_sample, index=False)
    print(f"  ✓ Saved regional grid (50,000 pts Parquet): {grid_parquet} ({os.path.getsize(grid_parquet) / (1024*1024):.2f} MB)")
    print(f"  ✓ Saved regional sample (10,000 pts CSV):   {grid_csv_sample} ({os.path.getsize(grid_csv_sample) / (1024*1024):.2f} MB)")

    print("\n" + "=" * 65)
    print(f"ML FEATURE EXTRACTION COMPLETE in {time.time() - start_time:.1f}s")
    print(f"Output Directory: {OUT_DIR}")
    print("=" * 65)


if __name__ == "__main__":
    main()
