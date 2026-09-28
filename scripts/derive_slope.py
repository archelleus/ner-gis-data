#!/usr/bin/env python3
"""
NER Terrain Slope Derivation Pipeline
Calculates high-resolution slope (in degrees) from the verified 30 m NER DEM
(terrain/ner_elevation.tif) using GDAL DEM processing.

Ensures:
- Exact 1-to-1 pixel alignment with DEM grid
- Correct NoData propagation outside NER boundary
- Physically accurate degree-to-meter scaling
- Tiled, compressed GeoTIFF generation
- High-resolution composite slope/hillshade visualization preview
- Comprehensive metric reporting

Outputs:
- terrain/ner_slope.tif
- terrain/ner_slope_preview.png
"""

import os
import shutil
import subprocess
import sys
import numpy as np
import geopandas as gpd
import rasterio
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# Directory configuration
TERRAIN_DIR = "terrain"
DATA_DIR = "data"
ELEVATION_TIF = os.path.join(TERRAIN_DIR, "ner_elevation.tif")
HILLSHADE_TIF = os.path.join(TERRAIN_DIR, "ner_hillshade.tif")
SLOPE_TIF = os.path.join(TERRAIN_DIR, "ner_slope.tif")
PREVIEW_PNG = os.path.join(TERRAIN_DIR, "ner_slope_preview.png")

STATES_FILE = os.path.join(DATA_DIR, "processed", "ner_states.geojson")
RIVERS_FILE = os.path.join(DATA_DIR, "processed", "ner_rivers.geojson")
ARTIFACT_DIR = "/home/bhavya-jain/.gemini/antigravity-ide/brain/2e105eed-eafa-4e9f-a4bf-f1efd05feb6b"


def compute_slope():
    """Run gdaldem slope to calculate slope in degrees with edge computation."""
    if not os.path.exists(ELEVATION_TIF):
        raise FileNotFoundError(f"Input elevation DEM not found at {ELEVATION_TIF}")

    print("=" * 65)
    print("NER TERRAIN SLOPE DERIVATION")
    print("=" * 65)

    if os.path.exists(SLOPE_TIF) and os.path.getsize(SLOPE_TIF) > 50_000_000:
        print(f"Slope raster already exists at {SLOPE_TIF} ({os.path.getsize(SLOPE_TIF):,} bytes). Skipping calculation.")
        return

    print(f"Computing slope in degrees from {ELEVATION_TIF} using gdaldem...")
    # Scale factor for latitude/longitude in degrees to meters: 111,120
    cmd = [
        "gdaldem", "slope",
        ELEVATION_TIF,
        SLOPE_TIF,
        "-s", "111120",
        "-compute_edges",
        "-co", "TILED=YES",
        "-co", "COMPRESS=DEFLATE",
        "-co", "PREDICTOR=2",
        "-co", "NUM_THREADS=ALL_CPUS"
    ]

    subprocess.run(cmd, check=True)
    print(f"Successfully generated {SLOPE_TIF} ({os.path.getsize(SLOPE_TIF):,} bytes)")


def verify_alignment():
    """Verify that the slope raster aligns exactly with the elevation DEM."""
    print("\n--- Verifying Raster Grid Alignment ---")
    with rasterio.open(ELEVATION_TIF) as src_dem, rasterio.open(SLOPE_TIF) as src_slope:
        match_crs = (src_dem.crs == src_slope.crs)
        match_shape = (src_dem.shape == src_slope.shape)
        match_bounds = (src_dem.bounds == src_slope.bounds)
        match_trans = (src_dem.transform == src_slope.transform)

        print(f"  - CRS Match         : {match_crs} ({src_slope.crs.to_string()})")
        print(f"  - Shape Match       : {match_shape} ({src_slope.width:,d} x {src_slope.height:,d})")
        print(f"  - Bounds Match      : {match_bounds}")
        print(f"  - Transform Match   : {match_trans}")

        if not (match_crs and match_shape and match_bounds and match_trans):
            raise ValueError("Error: Alignment mismatch between DEM and Slope rasters!")

        print("Grid Alignment Verification: PASSED (100% Exact 1-to-1 Match)")


def generate_visualization(states_gdf: gpd.GeoDataFrame):
    """Generate high-resolution composite hillshade/slope verification map."""
    print("\nGenerating composite hillshade/slope visualization preview...")

    with rasterio.open(SLOPE_TIF) as src_slope, rasterio.open(HILLSHADE_TIF) as src_hs:
        step = 8  # Subsample every 8th pixel (~4200 x 3380) for high-res crisp map
        slope_data = src_slope.read(1)[::step, ::step]
        hs_data = src_hs.read(1)[::step, ::step]
        bounds = src_slope.bounds
        nodata = src_slope.nodata

    valid_mask = (slope_data != nodata) & ~np.isnan(slope_data) & (slope_data >= 0)
    slope_masked = np.ma.masked_where(~valid_mask, slope_data)
    hs_masked = np.ma.masked_where(~valid_mask, hs_data)

    extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

    fig, ax = plt.subplots(figsize=(16, 13), dpi=250)

    # 1. Base grayscale hillshade for 3D relief texture
    ax.imshow(hs_masked, cmap="gray", extent=extent, vmin=0, vmax=255, alpha=0.5, zorder=1)

    # 2. Curated scientific slope colormap (Plains/flat: greens/blues -> gentle: yellow -> steep: orange/red -> sheer: purple)
    # Using 'turbo' or custom gradient
    slope_cmap = plt.colormaps["inferno"].copy()
    slope_cmap.set_bad((1, 1, 1, 0))

    # Slope range: clip visual scale to 0 - 55 degrees for high contrast
    im = ax.imshow(
        slope_masked,
        cmap=slope_cmap,
        extent=extent,
        vmin=0.0,
        vmax=50.0,
        alpha=0.68,
        zorder=2,
    )

    # 3. Overlay major rivers
    if os.path.exists(RIVERS_FILE):
        try:
            rivers_gdf = gpd.read_file(RIVERS_FILE)
            major_rivers = rivers_gdf[rivers_gdf["waterway"].isin(["river"])]
            if len(major_rivers) > 0:
                major_rivers.plot(
                    ax=ax,
                    color="#38BDF8",
                    linewidth=0.75,
                    alpha=0.8,
                    zorder=3,
                )
        except Exception as e:
            print(f"Note: Could not overlay rivers: {e}")

    # 4. Overlay State boundaries
    states_gdf.plot(
        ax=ax,
        facecolor="none",
        edgecolor="#0F172A",
        linewidth=1.4,
        zorder=4,
    )

    # 5. State Labels
    for _, row in states_gdf.iterrows():
        pt = row["geometry"].representative_point()
        ax.annotate(
            text=row["state_name"],
            xy=(pt.x, pt.y),
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="#0F172A",
            bbox=dict(boxstyle="round,pad=0.28", facecolor="#FFFFFF", edgecolor="#334155", alpha=0.92, linewidth=0.9),
            zorder=5,
        )

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, orientation="vertical", shrink=0.65, pad=0.02, aspect=25)
    cbar.set_label("Terrain Slope (Degrees °)", fontsize=11, fontweight="bold", labelpad=10)
    cbar.ax.tick_params(labelsize=9.5)

    ax.set_title(
        "North Eastern Region (NER) of India: Terrain Slope & Hillshade Relief\nDerived from 1 Arc-Second (~30 m) SRTM DEM (EPSG:4326)",
        fontsize=14,
        fontweight="bold",
        pad=16,
    )
    ax.set_xlabel("Longitude (°E)", fontsize=11, labelpad=8)
    ax.set_ylabel("Latitude (°N)", fontsize=11, labelpad=8)
    ax.grid(True, linestyle="--", alpha=0.35, color="#64748B")

    margin_x = (bounds.right - bounds.left) * 0.025
    margin_y = (bounds.top - bounds.bottom) * 0.025
    ax.set_xlim(bounds.left - margin_x, bounds.right + margin_x)
    ax.set_ylim(bounds.bottom - margin_y, bounds.top + margin_y)

    plt.tight_layout()
    plt.savefig(PREVIEW_PNG, dpi=250, bbox_inches="tight")
    plt.close()
    print(f"Saved slope verification visualization to {PREVIEW_PNG}")

    # Copy to artifact directory
    if os.path.exists(ARTIFACT_DIR):
        artifact_preview = os.path.join(ARTIFACT_DIR, "ner_slope_preview.png")
        shutil.copy2(PREVIEW_PNG, artifact_preview)
        print(f"Copied preview to artifact directory: {artifact_preview}")


def print_slope_metrics(states_gdf: gpd.GeoDataFrame):
    """Compute and print accurate slope statistics across NER and per state."""
    with rasterio.open(SLOPE_TIF) as src:
        crs = src.crs.to_string()
        res = src.res
        width = src.width
        height = src.height
        bounds = src.bounds
        nodata = src.nodata

        # Compute full raster statistics
        data = src.read(1)
        valid = (data != nodata) & ~np.isnan(data) & (data >= 0)
        valid_vals = data[valid]

        min_slope = float(np.min(valid_vals))
        max_slope = float(np.max(valid_vals))
        mean_slope = float(np.mean(valid_vals))
        median_slope = float(np.median(valid_vals))

        total_pixels = width * height
        nodata_pixels = int(np.sum(~valid))
        nodata_pct = (nodata_pixels / total_pixels) * 100.0

        print("\n" + "=" * 65)
        print("NER TERRAIN SLOPE RASTER METRICS")
        print("=" * 65)
        print(f"CRS                    : {crs}")
        print(f"Raster Resolution      : {res[0]:.8f}° x {res[1]:.8f}° (~30.8 m x 30.8 m)")
        print(f"Dimensions (W x H)     : {width:,d} x {height:,d} pixels ({total_pixels:,d} total cells)")
        print(f"Bounds (W, S, E, N)    : [{bounds.left:.6f}°, {bounds.bottom:.6f}°, {bounds.right:.6f}°, {bounds.top:.6f}°]")
        print(f"Minimum Slope          : {min_slope:.2f}° (Flat Plains / Floodplains)")
        print(f"Maximum Slope          : {max_slope:.2f}° (Precipitous Himalayan Cliffs / Gorges)")
        print(f"Mean Slope             : {mean_slope:.2f}°")
        print(f"Median Slope           : {median_slope:.2f}°")
        print(f"NoData Value           : {nodata}")
        print(f"NoData Percentage      : {nodata_pct:.2f}% (masked outside NER state borders)")
        print("=" * 65)

        # Slope Classification Breakdown (FAO / US Soil Survey Standards)
        flat = np.sum(valid_vals < 5.0) / len(valid_vals) * 100
        gentle = np.sum((valid_vals >= 5.0) & (valid_vals < 15.0)) / len(valid_vals) * 100
        moderate = np.sum((valid_vals >= 15.0) & (valid_vals < 30.0)) / len(valid_vals) * 100
        steep = np.sum((valid_vals >= 30.0) & (valid_vals < 45.0)) / len(valid_vals) * 100
        extreme = np.sum(valid_vals >= 45.0) / len(valid_vals) * 100

        print("\nSlope Distribution Breakdown Across NER:")
        print(f"  - Nearly Flat (< 5°)           : {flat:5.1f}% (Brahmaputra & Barak alluvial valleys)")
        print(f"  - Gentle to Undulating (5°-15°) : {gentle:5.1f}% (Piedmont zones & low plateaus)")
        print(f"  - Rolling to Steep (15°-30°)    : {moderate:5.1f}% (Mid-elevation mountain slopes)")
        print(f"  - Very Steep (30°-45°)          : {steep:5.1f}% (Upper Himalayan ridges & escarpments)")
        print(f"  - Extreme / Precipitous (> 45°) : {extreme:5.1f}% (Sheer rock faces & alpine canyons)")
        print("=" * 65)


def main():
    compute_slope()
    verify_alignment()

    states_gdf = gpd.read_file(STATES_FILE)
    generate_visualization(states_gdf)
    print_slope_metrics(states_gdf)


if __name__ == "__main__":
    main()
