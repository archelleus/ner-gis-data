#!/usr/bin/env python3
"""
NER District Administrative Boundaries Processor
Filters, clips, and validates district-level boundaries for all 8 NER states
from geoBoundaries ADM2 dataset.

Outputs:
- data/processed/ner_districts.geojson
- data/processed/ner_districts_preview.png
"""

import os
import shutil
import unicodedata
import requests
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
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

GEOBOUNDARIES_IND_ADM2_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/IND/ADM2/geoBoundaries-IND-ADM2.geojson"
)

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"
RAW_FILE = os.path.join(RAW_DIR, "geoBoundaries-IND-ADM2.geojson")
STATES_FILE = os.path.join(PROCESSED_DIR, "ner_states.geojson")
PROCESSED_DISTRICTS_FILE = os.path.join(PROCESSED_DIR, "ner_districts.geojson")
PREVIEW_FILE = os.path.join(PROCESSED_DIR, "ner_districts_preview.png")
ARTIFACT_DIR = "/home/bhavya-jain/.gemini/antigravity-ide/brain/2e105eed-eafa-4e9f-a4bf-f1efd05feb6b"


def normalize_name(name: str) -> str:
    """Normalize string by removing unicode diacritics."""
    if not isinstance(name, str):
        return ""
    normalized = unicodedata.normalize("NFD", name)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").strip()


def download_raw_data(url: str, output_path: str):
    """Download raw administrative data if not already cached."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
        print(f"Using cached raw district boundary dataset at {output_path} ({os.path.getsize(output_path):,} bytes)")
        return

    print(f"Downloading raw district boundary data from {url} ...")
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
    print(f"Saved raw boundary data to {output_path} ({os.path.getsize(output_path):,} bytes)")


def process_ner_districts():
    download_raw_data(GEOBOUNDARIES_IND_ADM2_URL, RAW_FILE)

    if not os.path.exists(STATES_FILE):
        raise FileNotFoundError(f"State boundaries file not found at {STATES_FILE}. Run fetch_and_process_boundaries.py first.")

    print(f"Loading processed NER states from {STATES_FILE}...")
    states_gdf = gpd.read_file(STATES_FILE)

    print(f"Loading raw India ADM2 districts from {RAW_FILE}...")
    districts_gdf = gpd.read_file(RAW_FILE)
    print(f"Total raw districts loaded: {len(districts_gdf)}")

    # Ensure projected CRS for accurate area calculation
    states_proj = states_gdf.to_crs("EPSG:7755")
    districts_proj = districts_gdf.to_crs("EPSG:7755")
    districts_gdf["orig_area"] = districts_proj.geometry.area

    # Filter candidate districts intersecting NER union
    ner_union_proj = states_proj.union_all()
    candidate_mask = districts_proj.intersects(ner_union_proj)
    candidates_proj = districts_proj[candidate_mask].copy()
    print(f"Districts geometrically intersecting NER boundary: {len(candidates_proj)}")

    # Overlay intersection to calculate exact area in each NER state
    overlay = gpd.overlay(candidates_proj, states_proj[["state_name", "geometry"]], how="intersection")
    overlay["int_area"] = overlay.geometry.area

    # Map original area to calculate overlap percentage
    area_map = districts_gdf.set_index("shapeID")["orig_area"].to_dict()
    overlay["overlap_pct"] = (overlay["int_area"] / overlay["shapeID"].map(area_map)) * 100.0

    # Pick state with maximum overlap for each district
    top_overlap = overlay.sort_values("int_area", ascending=False).drop_duplicates("shapeID")

    # Filter out external districts touching the border (like West Bengal districts with < 5% overlap)
    # Target NER districts have > 90% overlap with their state
    external_border_districts = top_overlap[top_overlap["overlap_pct"] < 50.0]
    ner_match = top_overlap[top_overlap["overlap_pct"] >= 50.0].copy()

    print("\n--- Integrity & Filter Checks ---")
    print(f"Border districts detected outside NER states (excluded): {len(external_border_districts)}")
    for _, row in external_border_districts.iterrows():
        print(f"  Excluded external district: {row['shapeName']} (overlap with {row['state_name']} was only {row['overlap_pct']:.2f}%)")

    # Merge matched state info with original district data in EPSG:4326
    ner_districts = districts_gdf.merge(
        ner_match[["shapeID", "state_name", "overlap_pct"]],
        on="shapeID",
        how="inner"
    )

    # Normalize district names
    ner_districts["district_name"] = ner_districts["shapeName"].apply(normalize_name)
    ner_districts["admin_level"] = "ADM2"

    # Check for duplicate districts
    dup_ids = ner_districts["shapeID"].duplicated().sum()
    dup_names = ner_districts.duplicated(subset=["state_name", "district_name"]).sum()
    print(f"Duplicate district IDs: {dup_ids}")
    print(f"Duplicate district names within state: {dup_names}")

    # Clip district geometries cleanly to their parent state boundary to eliminate any outer slivers
    print("\nClipping districts to parent state boundaries and validating geometries...")
    clipped_geometries = []
    for _, row in ner_districts.iterrows():
        st_geom = states_gdf[states_gdf["state_name"] == row["state_name"]].geometry.values[0]
        clipped = row["geometry"].intersection(st_geom)
        clipped = make_valid(clipped)
        # Retain only polygon/multipolygon elements
        if clipped.geom_type == "GeometryCollection":
            polys = [g for g in clipped.geoms if isinstance(g, (Polygon, MultiPolygon))]
            if polys:
                clipped = unary_union(polys)
            else:
                raise ValueError(f"Clipping resulted in non-polygon geometry for district: {row['district_name']}")
        clipped_geometries.append(clipped)

    ner_districts["geometry"] = clipped_geometries

    # Reconcile border slivers so districts perfectly tile 100% of their state boundary
    print("\nReconciling border slivers to achieve 100.0% topological alignment with state boundaries...")
    reconciled_geometries = {}
    for st_name in NER_STATES:
        st_geom = states_gdf[states_gdf["state_name"] == st_name].geometry.values[0]
        st_dists = ner_districts[ner_districts["state_name"] == st_name]
        dists_dict = {row["shapeID"]: row["geometry"] for _, row in st_dists.iterrows()}

        dists_union = unary_union(list(dists_dict.values()))
        diff = st_geom.difference(dists_union)

        if not diff.is_empty:
            if diff.geom_type == "Polygon":
                slivers = [diff]
            elif diff.geom_type == "MultiPolygon":
                slivers = list(diff.geoms)
            elif diff.geom_type == "GeometryCollection":
                slivers = [g for g in diff.geoms if isinstance(g, (Polygon, MultiPolygon))]
            else:
                slivers = []

            for sl in slivers:
                if sl.area < 1e-12:
                    continue
                best_id = None
                max_len = -1.0
                for d_id, d_geom in dists_dict.items():
                    shared = sl.boundary.intersection(d_geom.boundary)
                    if not shared.is_empty:
                        l = shared.length
                        if l > max_len:
                            max_len = l
                            best_id = d_id
                if best_id is None:
                    # Fallback: nearest district
                    min_d = float("inf")
                    for d_id, d_geom in dists_dict.items():
                        d = sl.distance(d_geom)
                        if d < min_d:
                            min_d = d
                            best_id = d_id
                dists_dict[best_id] = make_valid(dists_dict[best_id].union(sl))

        for d_id, d_geom in dists_dict.items():
            reconciled_geometries[d_id] = d_geom

    ner_districts["geometry"] = ner_districts["shapeID"].map(reconciled_geometries)

    # Validate all geometries
    invalid_count = (~ner_districts.geometry.is_valid).sum()
    print(f"Invalid geometries count after reconciliation: {invalid_count}")
    assert invalid_count == 0, f"Found {invalid_count} invalid geometries!"

    # Ensure CRS is EPSG:4326
    if ner_districts.crs is None or ner_districts.crs.to_string() != "EPSG:4326":
        ner_districts = ner_districts.to_crs("EPSG:4326")

    # Select standard attributes
    output_cols = [
        "district_name",
        "state_name",
        "admin_level",
        "shapeID",
        "geometry"
    ]
    ner_final = ner_districts[output_cols].copy()
    ner_final = ner_final.sort_values(by=["state_name", "district_name"]).reset_index(drop=True)

    # Save to data/processed/ner_districts.geojson
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    ner_final.to_file(PROCESSED_DISTRICTS_FILE, driver="GeoJSON")
    print(f"\nSaved processed NER districts to {PROCESSED_DISTRICTS_FILE}")

    # Print summary of districts in each state
    print("\n" + "=" * 60)
    print("NER DISTRICT ADMINISTRATIVE BOUNDARY SUMMARY")
    print("=" * 60)
    print(f"Total districts in NER: {len(ner_final)}")
    print(f"CRS: {ner_final.crs.to_string()}")
    print("\nNumber of districts per state:")
    state_counts = ner_final["state_name"].value_counts().sort_index()
    for state, count in state_counts.items():
        print(f"  - {state:<22}: {count:2d} districts")
    print(f"  {'Total':<22}: {len(ner_final):2d} districts")

    # Check for missing districts or states
    present_states = set(ner_final["state_name"].unique())
    missing_states = set(NER_STATES) - present_states
    print(f"\nMissing states in district dataset: {missing_states if missing_states else 'None (All 8 states covered)'}")

    # Total bounding box
    total_bounds = ner_final.total_bounds
    print(f"\nDistrict layer total bounding box:")
    print(f"  Min Longitude (West) : {total_bounds[0]:.6f}°")
    print(f"  Min Latitude  (South): {total_bounds[1]:.6f}°")
    print(f"  Max Longitude (East) : {total_bounds[2]:.6f}°")
    print(f"  Max Latitude  (North): {total_bounds[3]:.6f}°")
    print("=" * 60)

    # Generate preview map showing states and districts together
    generate_dual_preview_map(states_gdf, ner_final, PREVIEW_FILE)

    # Copy preview image to artifact dir
    if os.path.exists(ARTIFACT_DIR):
        artifact_preview = os.path.join(ARTIFACT_DIR, "ner_districts_preview.png")
        shutil.copy2(PREVIEW_FILE, artifact_preview)
        print(f"Copied preview map to artifact directory: {artifact_preview}")


def generate_dual_preview_map(states_gdf: gpd.GeoDataFrame, districts_gdf: gpd.GeoDataFrame, output_path: str):
    """Generate high-resolution preview map showing both state and district boundaries."""
    fig, ax = plt.subplots(figsize=(14, 12), dpi=250)

    # Color palette mapped by state
    state_colors = {
        "Arunachal Pradesh": "#B8D4E3",
        "Assam": "#FCE5CD",
        "Manipur": "#F4CCCC",
        "Meghalaya": "#D0E0E3",
        "Mizoram": "#D9EAD3",
        "Nagaland": "#FFF2CC",
        "Sikkim": "#EAD1DC",
        "Tripura": "#F9CB9C",
    }

    # Plot districts with state color theme
    districts_gdf = districts_gdf.copy()
    districts_gdf["color"] = districts_gdf["state_name"].map(state_colors).fillna("#EFEFEF")

    districts_gdf.plot(
        ax=ax,
        color=districts_gdf["color"],
        edgecolor="#666666",
        linewidth=0.55,
        linestyle="-",
        alpha=0.9,
    )

    # Overlay bold state boundaries
    states_gdf.plot(
        ax=ax,
        facecolor="none",
        edgecolor="#1E293B",
        linewidth=1.8,
    )

    # State label badges
    for _, row in states_gdf.iterrows():
        name = row["state_name"]
        rep_pt = row["geometry"].representative_point()
        ax.annotate(
            text=name,
            xy=(rep_pt.x, rep_pt.y),
            xytext=(0, 0),
            textcoords="offset points",
            ha="center",
            va="center",
            fontsize=10,
            fontweight="heavy",
            color="#0F172A",
            bbox=dict(
                boxstyle="round,pad=0.25",
                facecolor="#FFFFFF",
                edgecolor="#334155",
                alpha=0.92,
                linewidth=1.0,
            ),
        )

    # Format map display
    ax.set_title(
        "Administrative Boundaries: North Eastern Region (NER) of India\n8 States & 119 Districts (geoBoundaries ADM1 & ADM2 - EPSG:4326)",
        fontsize=14,
        fontweight="bold",
        pad=15,
    )
    ax.set_xlabel("Longitude (°E)", fontsize=11, labelpad=8)
    ax.set_ylabel("Latitude (°N)", fontsize=11, labelpad=8)

    ax.grid(True, linestyle="--", alpha=0.45, color="#94A3B8")

    bounds = states_gdf.total_bounds
    margin_x = (bounds[2] - bounds[0]) * 0.04
    margin_y = (bounds[3] - bounds[1]) * 0.04
    ax.set_xlim(bounds[0] - margin_x, bounds[2] + margin_x)
    ax.set_ylim(bounds[1] - margin_y, bounds[3] + margin_y)

    plt.tight_layout()
    plt.savefig(output_path, dpi=250, bbox_inches="tight")
    plt.close()
    print(f"Generated dual-layer preview map at {output_path}")


if __name__ == "__main__":
    process_ner_districts()
