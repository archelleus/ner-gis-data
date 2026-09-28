#!/usr/bin/env python3
"""
NER OSM Layers Processor: Transportation, Settlements, and Hydrography
Acquires OpenStreetMap data for the North Eastern Region of India,
cleans, validates geometries, clips to NER bounds, preserves key attributes,
and generates processed GeoJSON layers and a composite visualization map.

Outputs:
- data/raw/osm_roads_raw.json
- data/raw/osm_settlements_raw.json
- data/raw/osm_rivers_raw.json
- data/processed/ner_roads.geojson
- data/processed/ner_settlements.geojson
- data/processed/ner_rivers.geojson
- data/processed/ner_composite_preview.png
"""

import json
import os
import shutil
import time
from typing import Any, Dict, List, Optional
import requests
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
from shapely.geometry import LineString, Point, MultiLineString
from shapely.validation import make_valid

# Directory structure
RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"
ARTIFACT_DIR = "/home/bhavya-jain/.gemini/antigravity-ide/brain/2e105eed-eafa-4e9f-a4bf-f1efd05feb6b"

STATES_FILE = os.path.join(PROCESSED_DIR, "ner_states.geojson")
DISTRICTS_FILE = os.path.join(PROCESSED_DIR, "ner_districts.geojson")

RAW_ROADS_FILE = os.path.join(RAW_DIR, "osm_roads_raw.json")
RAW_SETTLEMENTS_FILE = os.path.join(RAW_DIR, "osm_settlements_raw.json")
RAW_RIVERS_FILE = os.path.join(RAW_DIR, "osm_rivers_raw.json")

PROCESSED_ROADS_FILE = os.path.join(PROCESSED_DIR, "ner_roads.geojson")
PROCESSED_SETTLEMENTS_FILE = os.path.join(PROCESSED_DIR, "ner_settlements.geojson")
PROCESSED_RIVERS_FILE = os.path.join(PROCESSED_DIR, "ner_rivers.geojson")
COMPOSITE_PREVIEW_FILE = os.path.join(PROCESSED_DIR, "ner_composite_preview.png")

# Overpass API mirrors for resilient queries
OVERPASS_ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# NER bounding box with slight margin: (min_lat, min_lon, max_lat, max_lon)
BBOX_STR = "21.9,88.0,29.5,97.5"


def query_overpass(query: str, timeout: int = 150) -> Dict[str, Any]:
    """Execute Overpass query with failover and retries across multiple mirrors."""
    headers = {
        "User-Agent": "NER-GIS-Project/1.0 (academic research)",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    last_error = None
    for attempt in range(3):
        for ep in OVERPASS_ENDPOINTS:
            try:
                print(f"Querying {ep} (attempt {attempt + 1})...")
                resp = requests.post(
                    ep,
                    data={"data": query},
                    headers=headers,
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    elements = data.get("elements", [])
                    print(f"  Success: fetched {len(elements):,} elements.")
                    return data
                else:
                    print(f"  {ep} returned HTTP {resp.status_code}")
            except Exception as e:
                print(f"  {ep} error: {e}")
                last_error = e
            time.sleep(3)
        time.sleep(5)
    raise RuntimeError(f"All Overpass endpoints failed: {last_error}")


# ==========================================
# 1. ROADS (Transportation)
# ==========================================

def fetch_and_process_roads(states_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Fetch, filter, clean, and clip major roads across NER."""
    os.makedirs(RAW_DIR, exist_ok=True)

    if os.path.exists(RAW_ROADS_FILE) and os.path.getsize(RAW_ROADS_FILE) > 10000:
        print(f"\nUsing cached raw roads from {RAW_ROADS_FILE} ({os.path.getsize(RAW_ROADS_FILE):,} bytes)")
        with open(RAW_ROADS_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    else:
        print("\nFetching OSM roads (motorway, trunk, primary, secondary, named tertiary)...")
        # Query in two focused blocks to avoid server timeout on large result sets
        q1 = f"""[out:json][timeout:150];
(
  way["highway"~"motorway|trunk|primary"]({BBOX_STR});
);
out geom;
"""
        q2 = f"""[out:json][timeout:150];
(
  way["highway"="secondary"]({BBOX_STR});
  way["highway"="tertiary"][name]({BBOX_STR});
);
out geom;
"""
        res1 = query_overpass(q1, timeout=150)
        time.sleep(4)
        res2 = query_overpass(q2, timeout=150)

        combined_elements = res1.get("elements", []) + res2.get("elements", [])
        raw_data = {"elements": combined_elements}
        with open(RAW_ROADS_FILE, "w", encoding="utf-8") as f:
            json.dump(raw_data, f)
        print(f"Saved raw roads to {RAW_ROADS_FILE}")

    # Parse OSM way elements into LineStrings
    features = []
    for el in raw_data.get("elements", []):
        if el.get("type") != "way":
            continue
        geom_points = el.get("geometry", [])
        if len(geom_points) < 2:
            continue
        coords = [(pt["lon"], pt["lat"]) for pt in geom_points]
        line = LineString(coords)
        if not line.is_valid:
            line = make_valid(line)
        if line.is_empty:
            continue

        tags = el.get("tags", {})
        features.append({
            "osm_id": el["id"],
            "name": tags.get("name", tags.get("name:en", "")),
            "ref": tags.get("ref", ""),
            "road_type": tags.get("highway", "unclassified"),
            "surface": tags.get("surface", ""),
            "geometry": line,
        })

    gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
    print(f"Raw road lines created: {len(gdf):,}")

    # Remove duplicates
    gdf = gdf.drop_duplicates(subset=["osm_id"]).copy()

    # Clip to NER boundary
    ner_boundary = states_gdf.union_all()
    print("Clipping roads to NER state boundary...")
    gdf = gpd.clip(gdf, ner_boundary)

    # Filter out empty or non-line geometries resulting from clipping
    gdf = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    # Spatial join to associate state_name
    gdf_centroids = gdf.geometry.representative_point()
    state_join = gpd.sjoin(
        gpd.GeoDataFrame(gdf[["osm_id"]], geometry=gdf_centroids, crs="EPSG:4326"),
        states_gdf[["state_name", "geometry"]],
        how="left",
        predicate="within"
    )
    state_map = state_join.drop_duplicates(subset=["osm_id"]).set_index("osm_id")["state_name"].to_dict()
    gdf["state_name"] = gdf["osm_id"].map(state_map).fillna("NER Border")

    # Validate geometries
    gdf["geometry"] = gdf["geometry"].apply(make_valid)
    assert gdf.geometry.is_valid.all(), "Invalid road geometries detected!"

    # Sort & reset index
    road_priority = {"motorway": 1, "trunk": 2, "primary": 3, "secondary": 4, "tertiary": 5}
    gdf["priority"] = gdf["road_type"].map(road_priority).fillna(9)
    gdf = gdf.sort_values(by=["priority", "state_name", "name"]).drop(columns=["priority"]).reset_index(drop=True)

    # Save processed GeoJSON
    gdf.to_file(PROCESSED_ROADS_FILE, driver="GeoJSON")
    print(f"Saved processed NER roads to {PROCESSED_ROADS_FILE} ({len(gdf):,} segments)")
    return gdf


# ==========================================
# 2. SETTLEMENTS (Populated Places)
# ==========================================

def fetch_and_process_settlements(states_gdf: gpd.GeoDataFrame, districts_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Fetch, filter, clean, and clip settlements across NER."""
    os.makedirs(RAW_DIR, exist_ok=True)

    if os.path.exists(RAW_SETTLEMENTS_FILE) and os.path.getsize(RAW_SETTLEMENTS_FILE) > 10000:
        print(f"\nUsing cached raw settlements from {RAW_SETTLEMENTS_FILE} ({os.path.getsize(RAW_SETTLEMENTS_FILE):,} bytes)")
        with open(RAW_SETTLEMENTS_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    else:
        print("\nFetching OSM settlements (cities, towns, villages, hamlets)...")
        q = f"""[out:json][timeout:150];
(
  node["place"~"city|town"]({BBOX_STR});
  node["place"="village"][name]({BBOX_STR});
  node["place"="hamlet"][name]({BBOX_STR});
);
out body;
"""
        raw_data = query_overpass(q, timeout=150)
        with open(RAW_SETTLEMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(raw_data, f)
        print(f"Saved raw settlements to {RAW_SETTLEMENTS_FILE}")

    # Parse node elements into Points
    features = []
    for el in raw_data.get("elements", []):
        if el.get("type") != "node":
            continue
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            continue

        tags = el.get("tags", {})
        name = tags.get("name", tags.get("name:en", "")).strip()
        place_type = tags.get("place", "locality")
        population = tags.get("population", "")

        features.append({
            "osm_id": el["id"],
            "name": name,
            "settlement_type": place_type,
            "population": population,
            "geometry": Point(lon, lat),
        })

    gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
    print(f"Raw settlement points created: {len(gdf):,}")

    # Remove duplicates
    gdf = gdf.drop_duplicates(subset=["osm_id"]).copy()

    # Spatial join with NER states to keep only points inside NER
    print("Filtering settlements strictly within NER boundaries...")
    settlements_in_states = gpd.sjoin(
        gdf,
        states_gdf[["state_name", "geometry"]],
        how="inner",
        predicate="within"
    )
    settlements_in_states = settlements_in_states.drop(columns=["index_right"])

    # Spatial join with NER districts to attach district_name
    settlements_with_districts = gpd.sjoin(
        settlements_in_states,
        districts_gdf[["district_name", "geometry"]],
        how="left",
        predicate="within"
    )
    settlements_with_districts = settlements_with_districts.drop(columns=["index_right"])
    settlements_final = settlements_with_districts.drop_duplicates(subset=["osm_id"]).copy()

    # Validate geometries
    assert settlements_final.geometry.is_valid.all(), "Invalid settlement geometries found!"

    # Sort: cities first, then towns, then villages
    rank_order = {"city": 1, "town": 2, "village": 3, "hamlet": 4}
    settlements_final["rank"] = settlements_final["settlement_type"].map(rank_order).fillna(5)
    settlements_final = settlements_final.sort_values(by=["rank", "state_name", "name"]).drop(columns=["rank"]).reset_index(drop=True)

    # Save processed GeoJSON
    settlements_final.to_file(PROCESSED_SETTLEMENTS_FILE, driver="GeoJSON")
    print(f"Saved processed NER settlements to {PROCESSED_SETTLEMENTS_FILE} ({len(settlements_final):,} locations)")
    return settlements_final


# ==========================================
# 3. RIVERS (Hydrography)
# ==========================================

def fetch_and_process_rivers(states_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Fetch, filter, clean, and clip rivers across NER."""
    os.makedirs(RAW_DIR, exist_ok=True)

    if os.path.exists(RAW_RIVERS_FILE) and os.path.getsize(RAW_RIVERS_FILE) > 10000:
        print(f"\nUsing cached raw rivers from {RAW_RIVERS_FILE} ({os.path.getsize(RAW_RIVERS_FILE):,} bytes)")
        with open(RAW_RIVERS_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    else:
        print("\nFetching OSM rivers and waterways...")
        q = f"""[out:json][timeout:150];
(
  way["waterway"="river"]({BBOX_STR});
  way["waterway"="stream"][name]({BBOX_STR});
);
out geom;
"""
        raw_data = query_overpass(q, timeout=150)
        with open(RAW_RIVERS_FILE, "w", encoding="utf-8") as f:
            json.dump(raw_data, f)
        print(f"Saved raw rivers to {RAW_RIVERS_FILE}")

    # Parse OSM way elements into LineStrings
    features = []
    for el in raw_data.get("elements", []):
        if el.get("type") != "way":
            continue
        geom_points = el.get("geometry", [])
        if len(geom_points) < 2:
            continue
        coords = [(pt["lon"], pt["lat"]) for pt in geom_points]
        line = LineString(coords)
        if not line.is_valid:
            line = make_valid(line)
        if line.is_empty:
            continue

        tags = el.get("tags", {})
        features.append({
            "osm_id": el["id"],
            "name": tags.get("name", tags.get("name:en", "")),
            "waterway": tags.get("waterway", "river"),
            "geometry": line,
        })

    gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")
    print(f"Raw river lines created: {len(gdf):,}")

    # Deduplicate
    gdf = gdf.drop_duplicates(subset=["osm_id"]).copy()

    # Clip to NER boundary
    ner_boundary = states_gdf.union_all()
    print("Clipping rivers to NER state boundary...")
    gdf = gpd.clip(gdf, ner_boundary)

    # Retain valid LineString / MultiLineString
    gdf = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
    gdf = gdf[~gdf.geometry.is_empty].copy()

    # Spatial join to tag state_name
    gdf_rep = gdf.geometry.representative_point()
    state_join = gpd.sjoin(
        gpd.GeoDataFrame(gdf[["osm_id"]], geometry=gdf_rep, crs="EPSG:4326"),
        states_gdf[["state_name", "geometry"]],
        how="left",
        predicate="within"
    )
    state_map = state_join.drop_duplicates(subset=["osm_id"]).set_index("osm_id")["state_name"].to_dict()
    gdf["state_name"] = gdf["osm_id"].map(state_map).fillna("Interstate River")

    # Validate geometries
    gdf["geometry"] = gdf["geometry"].apply(make_valid)
    assert gdf.geometry.is_valid.all(), "Invalid river geometries detected!"

    gdf = gdf.sort_values(by=["state_name", "name"]).reset_index(drop=True)

    # Save processed GeoJSON
    gdf.to_file(PROCESSED_RIVERS_FILE, driver="GeoJSON")
    print(f"Saved processed NER rivers to {PROCESSED_RIVERS_FILE} ({len(gdf):,} segments)")
    return gdf


# ==========================================
# 4. COMPOSITE PREVIEW MAP
# ==========================================

def generate_composite_preview_map(
    states_gdf: gpd.GeoDataFrame,
    districts_gdf: gpd.GeoDataFrame,
    roads_gdf: gpd.GeoDataFrame,
    settlements_gdf: gpd.GeoDataFrame,
    rivers_gdf: gpd.GeoDataFrame,
    output_path: str,
):
    """Generate high-resolution composite preview map showing all layers."""
    print("\nGenerating composite preview map...")
    fig, ax = plt.subplots(figsize=(15, 13), dpi=250)

    # 1. State background fills (subtle pastel tones)
    state_colors = {
        "Arunachal Pradesh": "#E8F0F7",
        "Assam": "#FEF7EE",
        "Manipur": "#FDF0EE",
        "Meghalaya": "#EDF5F6",
        "Mizoram": "#F0F7ED",
        "Nagaland": "#FFFDF0",
        "Sikkim": "#F7EDF4",
        "Tripura": "#FDF5ED",
    }
    states_styled = states_gdf.copy()
    states_styled["color"] = states_styled["state_name"].map(state_colors).fillna("#F8FAFC")
    states_styled.plot(
        ax=ax,
        color=states_styled["color"],
        edgecolor="#334155",
        linewidth=1.4,
        zorder=1,
    )

    # 2. District boundaries (light dashed lines)
    districts_gdf.plot(
        ax=ax,
        facecolor="none",
        edgecolor="#94A3B8",
        linewidth=0.5,
        linestyle=":",
        alpha=0.8,
        zorder=2,
    )

    # 3. Rivers layer (hydrology in crisp azure blue)
    rivers_gdf.plot(
        ax=ax,
        color="#0284C7",
        linewidth=0.85,
        alpha=0.75,
        label="Rivers & Waterways",
        zorder=3,
    )

    # 4. Roads layer (hierarchical styling: trunk/motorway > primary > secondary)
    motorways_trunks = roads_gdf[roads_gdf["road_type"].isin(["motorway", "trunk"])]
    primaries = roads_gdf[roads_gdf["road_type"] == "primary"]
    secondaries = roads_gdf[roads_gdf["road_type"].isin(["secondary", "tertiary"])]

    if not secondaries.empty:
        secondaries.plot(
            ax=ax,
            color="#EA580C",
            linewidth=0.6,
            alpha=0.65,
            label="Secondary / Regional Roads",
            zorder=4,
        )
    if not primaries.empty:
        primaries.plot(
            ax=ax,
            color="#D97706",
            linewidth=1.0,
            alpha=0.85,
            label="Primary Roads (State Arterials)",
            zorder=5,
        )
    if not motorways_trunks.empty:
        motorways_trunks.plot(
            ax=ax,
            color="#DC2626",
            linewidth=1.3,
            alpha=0.9,
            label="National Highways / Expressways",
            zorder=6,
        )

    # 5. Settlements layer (hierarchical points: cities, towns)
    cities = settlements_gdf[settlements_gdf["settlement_type"] == "city"]
    towns = settlements_gdf[settlements_gdf["settlement_type"] == "town"]

    if not towns.empty:
        towns.plot(
            ax=ax,
            color="#6366F1",
            markersize=14,
            alpha=0.6,
            label="Towns",
            zorder=7,
        )
    if not cities.empty:
        cities.plot(
            ax=ax,
            color="#1E1B4B",
            edgecolor="#FFFFFF",
            linewidth=0.8,
            markersize=35,
            alpha=0.95,
            label="Major Cities",
            zorder=8,
        )
        # Label prominent cities
        for _, row in cities.head(15).iterrows():
            pt = row["geometry"]
            ax.annotate(
                text=row["name"],
                xy=(pt.x, pt.y),
                xytext=(3, 3),
                textcoords="offset points",
                fontsize=7.5,
                fontweight="bold",
                color="#0F172A",
                bbox=dict(boxstyle="round,pad=0.18", facecolor="#FFFFFF", alpha=0.85, edgecolor="#64748B", linewidth=0.5),
                zorder=9,
            )

    # Title and axis styling
    ax.set_title(
        "North Eastern Region (NER) GIS Composite Overview\nStates, Districts, Roads, Settlements, and Hydrography (EPSG:4326)",
        fontsize=14,
        fontweight="bold",
        pad=16,
    )
    ax.set_xlabel("Longitude (°E)", fontsize=11, labelpad=8)
    ax.set_ylabel("Latitude (°N)", fontsize=11, labelpad=8)
    ax.grid(True, linestyle="--", alpha=0.45, color="#94A3B8")

    # Zoom frame with margins
    bounds = states_gdf.total_bounds
    margin_x = (bounds[2] - bounds[0]) * 0.03
    margin_y = (bounds[3] - bounds[1]) * 0.03
    ax.set_xlim(bounds[0] - margin_x, bounds[2] + margin_x)
    ax.set_ylim(bounds[1] - margin_y, bounds[3] + margin_y)

    ax.legend(loc="lower right", framealpha=0.92, edgecolor="#CBD5E1", fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=250, bbox_inches="tight")
    plt.close()
    print(f"Generated composite preview map at {output_path}")


# ==========================================
# MAIN WORKFLOW
# ==========================================

def main():
    print("=" * 60)
    print("NER GIS OSM LAYERS PIPELINE")
    print("=" * 60)

    # Load baseline administrative boundaries
    if not os.path.exists(STATES_FILE) or not os.path.exists(DISTRICTS_FILE):
        raise FileNotFoundError("Prerequisite state/district files missing! Run Step 1 and Step 2 scripts first.")

    states_gdf = gpd.read_file(STATES_FILE)
    districts_gdf = gpd.read_file(DISTRICTS_FILE)

    # 1. Process Roads
    roads_gdf = fetch_and_process_roads(states_gdf)

    # 2. Process Settlements
    settlements_gdf = fetch_and_process_settlements(states_gdf, districts_gdf)

    # 3. Process Rivers
    rivers_gdf = fetch_and_process_rivers(states_gdf)

    # Summary report
    print("\n" + "=" * 60)
    print("SUMMARY OF GENERATED OSM LAYERS")
    print("=" * 60)
    print(f"1. Roads Layer       : {len(roads_gdf):,d} features")
    print(f"   - Motorway/Trunk  : {len(roads_gdf[roads_gdf['road_type'].isin(['motorway', 'trunk'])]):,d}")
    print(f"   - Primary         : {len(roads_gdf[roads_gdf['road_type'] == 'primary']):,d}")
    print(f"   - Secondary       : {len(roads_gdf[roads_gdf['road_type'] == 'secondary']):,d}")
    print(f"   - Tertiary/Other  : {len(roads_gdf[roads_gdf['road_type'].isin(['tertiary', 'unclassified'])]):,d}")
    print(f"   - CRS             : {roads_gdf.crs.to_string()}")

    print(f"\n2. Settlements Layer : {len(settlements_gdf):,d} features")
    print(f"   - Cities          : {len(settlements_gdf[settlements_gdf['settlement_type'] == 'city']):,d}")
    print(f"   - Towns           : {len(settlements_gdf[settlements_gdf['settlement_type'] == 'town']):,d}")
    print(f"   - Villages/Hamlets: {len(settlements_gdf[settlements_gdf['settlement_type'].isin(['village', 'hamlet'])]):,d}")
    print(f"   - CRS             : {settlements_gdf.crs.to_string()}")

    print(f"\n3. Rivers Layer      : {len(rivers_gdf):,d} features")
    print(f"   - Named waterways : {len(rivers_gdf[rivers_gdf['name'] != '']):,d}")
    print(f"   - Unnamed streams : {len(rivers_gdf[rivers_gdf['name'] == '']):,d}")
    print(f"   - CRS             : {rivers_gdf.crs.to_string()}")
    print("=" * 60)

    # Generate composite preview map
    generate_composite_preview_map(
        states_gdf, districts_gdf, roads_gdf, settlements_gdf, rivers_gdf, COMPOSITE_PREVIEW_FILE
    )

    # Copy to artifact directory
    if os.path.exists(ARTIFACT_DIR):
        artifact_preview = os.path.join(ARTIFACT_DIR, "ner_composite_preview.png")
        shutil.copy2(COMPOSITE_PREVIEW_FILE, artifact_preview)
        print(f"Copied composite preview to artifact directory: {artifact_preview}")


if __name__ == "__main__":
    main()
