"""
NER ML Feature Extractor for Custom Coordinates / Landslide Inventories
=======================================================================
Takes arbitrary geographic coordinates (Latitude, Longitude in WGS84)
and extracts the identical set of topographic and proximity features:
  - elevation_m (from 30m DEM)
  - slope_deg & slope_class (from 30m Slope Raster)
  - aspect_deg & aspect_direction (Horn's 3x3 finite-difference algorithm)
  - dist_to_road_m (Euclidean distance to nearest road network in UTM 46N)
  - dist_to_river_m (Euclidean distance to nearest river channel in UTM 46N)
  - dist_to_settlement_m (Euclidean distance to nearest settlement in UTM 46N)
  - state_name & district_name (Spatial polygon intersection)

Usage via CLI:
  python extract_features_for_points.py input_coordinates.csv output_features.csv

Usage in Python:
  from extract_features_for_points import extract_features_for_df
  enriched_df = extract_features_for_df(df, lat_col="latitude", lon_col="longitude")
"""

import sys
import os
import argparse
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString
from scipy.spatial import cKDTree
import rasterio

# Resolve root repo directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data", "processed")
TERRAIN_DIR = os.path.join(REPO_ROOT, "terrain")

DEM_FILE = os.path.join(TERRAIN_DIR, "ner_elevation.tif")
SLOPE_FILE = os.path.join(TERRAIN_DIR, "ner_slope.tif")
DISTRICTS_FILE = os.path.join(DATA_DIR, "ner_districts.geojson")
ROADS_FILE = os.path.join(DATA_DIR, "ner_roads.geojson")
RIVERS_FILE = os.path.join(DATA_DIR, "ner_rivers.geojson")
SETTLEMENTS_FILE = os.path.join(DATA_DIR, "ner_settlements.geojson")

METRIC_CRS = "EPSG:32646"


def classify_slope(slope_deg):
    if slope_deg is None or np.isnan(slope_deg) or slope_deg < 0:
        return "Unknown"
    if slope_deg < 5.0:
        return "Flat (<5°)"
    elif slope_deg < 15.0:
        return "Gentle (5°-15°)"
    elif slope_deg < 30.0:
        return "Moderate (15°-30°)"
    elif slope_deg < 45.0:
        return "Steep (30°-45°)"
    else:
        return "Very Steep (>45°)"


def classify_aspect(aspect_deg):
    if aspect_deg is None or np.isnan(aspect_deg) or aspect_deg < 0:
        return "Flat / None"
    directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((aspect_deg + 22.5) % 360 // 45)
    return directions[idx]


def build_line_kdtree(gdf_metric, sample_interval_m=50):
    sample_points = []
    for geom in gdf_metric.geometry:
        if geom is None or geom.is_empty:
            continue
        lines = [geom] if isinstance(geom, LineString) else list(geom.geoms)
        for line in lines:
            length = line.length
            num_points = max(2, int(length // sample_interval_m) + 1)
            for d in np.linspace(0, length, num_points):
                pt = line.interpolate(d)
                sample_points.append((pt.x, pt.y))
    return cKDTree(np.array(sample_points, dtype=np.float64))


def extract_features_for_df(df, lat_col="latitude", lon_col="longitude"):
    """
    Extracts all topographic and infrastructural features for the coordinates in df.
    Returns enriched DataFrame.
    """
    df = df.copy()
    lats = df[lat_col].values
    lons = df[lon_col].values
    coords_lon_lat = list(zip(lons, lats))

    # 1. Raster sampling (Elevation & Slope)
    print("Sampling elevation & slope rasters...")
    with rasterio.open(DEM_FILE) as src:
        elev_vals = [float(v[0]) if v[0] != src.nodata and v[0] > -10000 else np.nan for v in src.sample(coords_lon_lat)]
    with rasterio.open(SLOPE_FILE) as src:
        slope_vals = [float(v[0]) if v[0] != src.nodata and v[0] >= 0 else np.nan for v in src.sample(coords_lon_lat)]

    # 2. Aspect computation via Horn's method
    print("Computing local aspect gradient...")
    aspect_vals = []
    with rasterio.open(DEM_FILE) as dem_src:
        inv_tf = ~dem_src.transform
        for lon, lat in zip(lons, lats):
            px, py = inv_tf * (lon, lat)
            col, row = int(round(px)), int(round(py))
            if row < 1 or row >= dem_src.height - 1 or col < 1 or col >= dem_src.width - 1:
                aspect_vals.append(np.nan)
                continue
            win = dem_src.read(1, window=((row - 1, row + 2), (col - 1, col + 2))).astype(np.float64)
            if win.shape != (3, 3):
                aspect_vals.append(np.nan)
                continue
            z1, z2, z3 = win[0, 0], win[0, 1], win[0, 2]
            z4, z5, z6 = win[1, 0], win[1, 1], win[1, 2]
            z7, z8, z9 = win[2, 0], win[2, 1], win[2, 2]
            dz_dx = ((z3 + 2.0 * z6 + z9) - (z1 + 2.0 * z4 + z7)) / 8.0
            dz_dy = ((z7 + 2.0 * z8 + z9) - (z1 + 2.0 * z2 + z3)) / 8.0
            if dz_dx == 0 and dz_dy == 0:
                aspect_vals.append(0.0)
            else:
                asp = np.degrees(np.arctan2(-dz_dx, dz_dy))
                if asp < 0:
                    asp += 360.0
                aspect_vals.append(round(asp, 1))

    # 3. Metric KDTree Proximity
    print("Querying road, river, and settlement distances...")
    pts_metric = gpd.GeoSeries(gpd.points_from_xy(lons, lats), crs="EPSG:4326").to_crs(METRIC_CRS)
    metric_coords = np.c_[pts_metric.geometry.x.values, pts_metric.geometry.y.values]

    roads_gdf = gpd.read_file(ROADS_FILE).to_crs(METRIC_CRS)
    road_tree = build_line_kdtree(roads_gdf)
    road_dists, _ = road_tree.query(metric_coords)

    rivers_gdf = gpd.read_file(RIVERS_FILE).to_crs(METRIC_CRS)
    river_tree = build_line_kdtree(rivers_gdf)
    river_dists, _ = river_tree.query(metric_coords)

    settlements_gdf = gpd.read_file(SETTLEMENTS_FILE).to_crs(METRIC_CRS)
    st_pts = np.c_[settlements_gdf.geometry.x.values, settlements_gdf.geometry.y.values]
    st_tree = cKDTree(st_pts)
    st_dists, _ = st_tree.query(metric_coords)

    # 4. District & State Spatial Attribution
    print("Spatial attribution to administrative polygons...")
    districts_gdf = gpd.read_file(DISTRICTS_FILE)
    pts_gdf = gpd.GeoDataFrame(geometry=gpd.points_from_xy(lons, lats), crs="EPSG:4326")
    joined = gpd.sjoin(pts_gdf, districts_gdf[["district_name", "state_name", "geometry"]], how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]

    df["state_name"] = joined["state_name"].values
    df["district_name"] = joined["district_name"].values
    df["elevation_m"] = np.round(elev_vals, 1)
    df["slope_deg"] = np.round(slope_vals, 2)
    df["slope_class"] = [classify_slope(s) for s in slope_vals]
    df["aspect_deg"] = np.round(aspect_vals, 1)
    df["aspect_direction"] = [classify_aspect(a) for a in aspect_vals]
    df["dist_to_road_m"] = np.round(road_dists, 1)
    df["dist_to_river_m"] = np.round(river_dists, 1)
    df["dist_to_settlement_m"] = np.round(st_dists, 1)

    return df


def main():
    parser = argparse.ArgumentParser(description="Extract ML terrain and proximity features for coordinate points")
    parser.add_argument("input_csv", help="Input CSV containing latitude and longitude columns")
    parser.add_argument("output_csv", help="Output path for enriched CSV")
    parser.add_argument("--lat-col", default="latitude", help="Name of latitude column (default: latitude)")
    parser.add_argument("--lon-col", default="longitude", help="Name of longitude column (default: longitude)")
    args = parser.parse_args()

    if not os.path.exists(args.input_csv):
        print(f"Error: input file '{args.input_csv}' not found.")
        sys.exit(1)

    df = pd.read_csv(args.input_csv)
    print(f"Loaded {len(df)} rows from {args.input_csv}")
    enriched = extract_features_for_df(df, lat_col=args.lat_col, lon_col=args.lon_col)
    enriched.to_csv(args.output_csv, index=False)
    print(f"Successfully saved enriched features to {args.output_csv}")


if __name__ == "__main__":
    main()
