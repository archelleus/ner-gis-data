#!/usr/bin/env python3
"""
NER Administrative Boundaries Processor
Downloads official ADM1 boundary data for India from geoBoundaries,
extracts and validates boundaries for all 8 North Eastern Region (NER) states:
Arunachal Pradesh, Assam, Manipur, Meghalaya, Mizoram, Nagaland, Sikkim, and Tripura.

Outputs:
- data/raw/geoBoundaries-IND-ADM1.geojson
- data/processed/ner_states.geojson
- data/processed/ner_states_preview.png
"""

import os
import shutil
import unicodedata
import requests
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.validation import make_valid

# Target 8 NER states
NER_STATES = [
    "Arunachal Pradesh",
    "Assam",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Sikkim",
    "Tripura"
]

GEOBOUNDARIES_IND_ADM1_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM1/geoBoundaries-IND-ADM1.geojson"
)

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"
RAW_FILE = os.path.join(RAW_DIR, "geoBoundaries-IND-ADM1.geojson")
PROCESSED_FILE = os.path.join(PROCESSED_DIR, "ner_states.geojson")
PREVIEW_FILE = os.path.join(PROCESSED_DIR, "ner_states_preview.png")
ARTIFACT_DIR = "/home/bhavya-jain/.gemini/antigravity-ide/brain/2e105eed-eafa-4e9f-a4bf-f1efd05feb6b"


def normalize_name(name: str) -> str:
    """Normalize string by removing unicode diacritics (e.g. Arunāchal -> Arunachal)."""
    if not isinstance(name, str):
        return ""
    normalized = unicodedata.normalize("NFD", name)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").strip()


def download_raw_data(url: str, output_path: str):
    """Download raw administrative data if not already cached."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        print(f"Using cached raw boundary dataset at {output_path} ({os.path.getsize(output_path):,} bytes)")
        return

    print(f"Downloading raw boundary data from {url} ...")
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
    print(f"Saved raw boundary data to {output_path} ({os.path.getsize(output_path):,} bytes)")


def process_ner_boundaries():
    download_raw_data(GEOBOUNDARIES_IND_ADM1_URL, RAW_FILE)

    print("Loading raw GeoJSON into GeoPandas...")
    gdf = gpd.read_file(RAW_FILE)

    # Normalize state names to match NER target names
    gdf["normalized_name"] = gdf["shapeName"].apply(normalize_name)

    # Filter for 8 NER states
    ner_gdf = gdf[gdf["normalized_name"].isin(NER_STATES)].copy()

    # Verify all 8 states are found
    found_states = set(ner_gdf["normalized_name"].tolist())
    missing_states = set(NER_STATES) - found_states
    if missing_states:
        raise ValueError(f"Missing expected NER states: {missing_states}")

    # Set clean attribute columns
    ner_gdf["state_name"] = ner_gdf["normalized_name"]
    ner_gdf = ner_gdf.sort_values(by="state_name").reset_index(drop=True)

    # Ensure EPSG:4326
    if ner_gdf.crs is None:
        print("Warning: CRS missing in raw data. Setting to EPSG:4326.")
        ner_gdf = ner_gdf.set_crs("EPSG:4326")
    elif ner_gdf.crs.to_string() != "EPSG:4326":
        print(f"Reprojecting from {ner_gdf.crs} to EPSG:4326...")
        ner_gdf = ner_gdf.to_crs("EPSG:4326")

    # Validate geometries
    print("\n--- Validating Geometries ---")
    invalid_mask = ~ner_gdf.geometry.is_valid
    if invalid_mask.any():
        print(f"Fixing {invalid_mask.sum()} invalid geometries using shapely.validation.make_valid...")
        ner_gdf["geometry"] = ner_gdf["geometry"].apply(make_valid)

    # Verify all are valid now
    assert ner_gdf.geometry.is_valid.all(), "Error: Some geometries remain invalid after repair!"
    print("All geometries successfully validated (100% valid).")

    # Select standard attributes
    keep_cols = ["state_name", "shapeISO", "shapeID", "geometry"]
    existing_cols = [c for c in keep_cols if c in ner_gdf.columns]
    ner_final = ner_gdf[existing_cols].copy()

    # Save to processed directory
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    ner_final.to_file(PROCESSED_FILE, driver="GeoJSON")
    print(f"\nSaved processed NER states to {PROCESSED_FILE}")

    # Print summary information required
    print("\n" + "=" * 50)
    print("NER ADMINISTRATIVE BOUNDARY COMPONENT SUMMARY")
    print("=" * 50)
    print(f"Number of states: {len(ner_final)}")
    print(f"State names: {', '.join(ner_final['state_name'].tolist())}")
    print(f"CRS: {ner_final.crs.to_string()}")

    print("\nGeometry types per state:")
    for _, row in ner_final.iterrows():
        print(f"  - {row['state_name']:<20}: {row['geometry'].geom_type}")

    total_bounds = ner_final.total_bounds
    print(f"\nTotal bounding box (minx, miny, maxx, maxy):")
    print(f"  Min Longitude (West) : {total_bounds[0]:.6f}°")
    print(f"  Min Latitude  (South): {total_bounds[1]:.6f}°")
    print(f"  Max Longitude (East) : {total_bounds[2]:.6f}°")
    print(f"  Max Latitude  (North): {total_bounds[3]:.6f}°")
    print(f"  Total bounds array   : {total_bounds.tolist()}")
    print("=" * 50)

    # Generate preview map
    generate_preview_map(ner_final, PREVIEW_FILE)

    # Copy preview image to artifact dir if present
    if os.path.exists(ARTIFACT_DIR):
        artifact_preview = os.path.join(ARTIFACT_DIR, "ner_states_preview.png")
        shutil.copy2(PREVIEW_FILE, artifact_preview)
        print(f"Copied preview to artifact directory: {artifact_preview}")


def generate_preview_map(gdf: gpd.GeoDataFrame, output_path: str):
    """Generate high-quality preview map of all 8 NER states."""
    fig, ax = plt.subplots(figsize=(12, 10), dpi=200)

    # Cohesive distinct colors for each state
    colors = [
        "#4E79A7",  # Arunachal Pradesh
        "#F28E2B",  # Assam
        "#E15759",  # Manipur
        "#76B7B2",  # Meghalaya
        "#59A14F",  # Mizoram
        "#EDC948",  # Nagaland
        "#B07AA1",  # Sikkim
        "#FF9DA7",  # Tripura
    ]

    gdf.plot(
        ax=ax,
        color=colors[: len(gdf)],
        edgecolor="#222222",
        linewidth=1.2,
        alpha=0.88,
    )

    label_offsets = {
        "Arunachal Pradesh": (0, 0),
        "Assam": (0, -0.1),
        "Manipur": (0, 0),
        "Meghalaya": (0, 0),
        "Mizoram": (0, 0),
        "Nagaland": (0, 0),
        "Sikkim": (0, 0),
        "Tripura": (0, 0),
    }

    for _, row in gdf.iterrows():
        name = row["state_name"]
        rep_pt = row["geometry"].representative_point()
        offset = label_offsets.get(name, (0, 0))
        x = rep_pt.x + offset[0]
        y = rep_pt.y + offset[1]

        ax.annotate(
            text=name,
            xy=(x, y),
            xytext=(0, 0),
            textcoords="offset points",
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="#111827",
            bbox=dict(
                boxstyle="round,pad=0.3",
                facecolor="white",
                edgecolor="#4B5563",
                alpha=0.85,
                linewidth=0.8,
            ),
        )

    ax.set_title(
        "Administrative Boundaries: North Eastern Region (NER) of India\n8 States (geoBoundaries ADM1 - EPSG:4326)",
        fontsize=14,
        fontweight="bold",
        pad=15,
    )
    ax.set_xlabel("Longitude (°E)", fontsize=11, labelpad=8)
    ax.set_ylabel("Latitude (°N)", fontsize=11, labelpad=8)

    ax.grid(True, linestyle="--", alpha=0.5, color="#888888")

    bounds = gdf.total_bounds
    margin_x = (bounds[2] - bounds[0]) * 0.05
    margin_y = (bounds[3] - bounds[1]) * 0.05
    ax.set_xlim(bounds[0] - margin_x, bounds[2] + margin_x)
    ax.set_ylim(bounds[1] - margin_y, bounds[3] + margin_y)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Generated preview map at {output_path}")


if __name__ == "__main__":
    process_ner_boundaries()
