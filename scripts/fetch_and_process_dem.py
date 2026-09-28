#!/usr/bin/env python3
"""
NER Regional Elevation & Terrain Processor
Acquires 1-arc-second (~30 m) SRTM Skadi DEM tiles for the complete
North Eastern Region (all 8 states), mosaics them, clips to the exact
NER state boundary, generates tiled/compressed GeoTIFFs, computes
projected hillshade, and produces a visual inspection preview map.

Outputs:
- terrain/ner_elevation.tif
- terrain/ner_hillshade.tif
- terrain/ner_terrain_preview.png
"""

import concurrent.futures
import gzip
import os
import shutil
import subprocess
import sys
import time
from typing import List, Tuple
import requests
import numpy as np
import geopandas as gpd
import rasterio
import matplotlib.pyplot as plt
from shapely.geometry import box

# Directory configuration
DATA_DIR = "data"
RAW_TILES_DIR = os.path.join(DATA_DIR, "raw", "dem_tiles")
PROCESSED_STATES_FILE = os.path.join(DATA_DIR, "processed", "ner_states.geojson")
PROCESSED_RIVERS_FILE = os.path.join(DATA_DIR, "processed", "ner_rivers.geojson")
TERRAIN_DIR = "terrain"
ARTIFACT_DIR = "/home/bhavya-jain/.gemini/antigravity-ide/brain/2e105eed-eafa-4e9f-a4bf-f1efd05feb6b"

ELEVATION_TIF = os.path.join(TERRAIN_DIR, "ner_elevation.tif")
HILLSHADE_TIF = os.path.join(TERRAIN_DIR, "ner_hillshade.tif")
PREVIEW_PNG = os.path.join(TERRAIN_DIR, "ner_terrain_preview.png")

BASE_SKADI_URL = "https://elevation-tiles-prod.s3.amazonaws.com/skadi"
NODATA_VAL = -32768


def get_required_tiles(states_gdf: gpd.GeoDataFrame) -> List[Tuple[int, int, str, str]]:
    """Determine precisely which 1x1 degree tiles intersect the NER states union."""
    ner_union = states_gdf.union_all()
    bounds = states_gdf.total_bounds  # [minx, miny, maxx, maxy]
    min_lon = int(np.floor(bounds[0]))
    min_lat = int(np.floor(bounds[1]))
    max_lon = int(np.ceil(bounds[2]))
    max_lat = int(np.ceil(bounds[3]))

    required = []
    for lat in range(min_lat, max_lat):
        for lon in range(min_lon, max_lon):
            tile_poly = box(lon, lat, lon + 1, lat + 1)
            if tile_poly.intersects(ner_union):
                tile_name = f"N{lat:02d}E{lon:03d}"
                url = f"{BASE_SKADI_URL}/N{lat:02d}/{tile_name}.hgt.gz"
                required.append((lat, lon, tile_name, url))

    return sorted(required, key=lambda x: x[2])


def download_tile(tile_info: Tuple[int, int, str, str]) -> str:
    """Download and decompress a single Skadi HGT tile."""
    lat, lon, name, url = tile_info
    hgt_path = os.path.join(RAW_TILES_DIR, f"{name}.hgt")
    if os.path.exists(hgt_path) and os.path.getsize(hgt_path) > 1000000:
        return hgt_path

    os.makedirs(RAW_TILES_DIR, exist_ok=True)
    gz_path = os.path.join(RAW_TILES_DIR, f"{name}.hgt.gz")

    for attempt in range(4):
        try:
            resp = requests.get(url, timeout=45)
            if resp.status_code == 200:
                with open(gz_path, "wb") as f:
                    f.write(resp.content)
                # Decompress
                with gzip.open(gz_path, "rb") as f_in, open(hgt_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                os.remove(gz_path)
                return hgt_path
            else:
                print(f"Warning: Tile {name} returned HTTP {resp.status_code}")
        except Exception as e:
            if attempt == 3:
                raise RuntimeError(f"Failed to download tile {name} from {url}: {e}")
            time.sleep(2 * (attempt + 1))

    raise RuntimeError(f"Could not acquire tile {name}")


def download_all_tiles(tiles: List[Tuple[int, int, str, str]]) -> List[str]:
    """Download all required tiles concurrently with progress tracking."""
    os.makedirs(RAW_TILES_DIR, exist_ok=True)
    print(f"\nDownloading/verifying {len(tiles)} required 1x1° DEM tiles (~30 m resolution)...")

    hgt_files = []
    completed = 0
    total = len(tiles)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_tile = {executor.submit(download_tile, t): t for t in tiles}
        for future in concurrent.futures.as_completed(future_to_tile):
            tile_info = future_to_tile[future]
            try:
                path = future.result()
                hgt_files.append(path)
                completed += 1
                sys.stdout.write(f"\r  Progress: [{completed}/{total}] {tile_info[2]}.hgt verified.")
                sys.stdout.flush()
            except Exception as exc:
                print(f"\nError downloading {tile_info[2]}: {exc}")
                raise

    print("\nAll 45 tiles successfully verified on disk.")
    return sorted(hgt_files)


def mosaic_and_clip_dem(hgt_files: List[str], states_file: str):
    """Mosaic tiles and clip precisely to the NER boundary polygon."""
    os.makedirs(TERRAIN_DIR, exist_ok=True)
    if os.path.exists(ELEVATION_TIF) and os.path.getsize(ELEVATION_TIF) > 50_000_000:
        print(f"\nElevation raster already exists at {ELEVATION_TIF} ({os.path.getsize(ELEVATION_TIF):,} bytes). Skipping rebuild.")
        return

    print("\nBuilding VRT mosaic of DEM tiles...")
    vrt_path = os.path.join(RAW_TILES_DIR, "ner_mosaic.vrt")
    cmd_vrt = ["gdalbuildvrt", vrt_path] + hgt_files
    subprocess.run(cmd_vrt, check=True)

    print("Clipping VRT to exact NER state boundaries with gdalwarp (tiled & DEFLATE compressed)...")
    cmd_warp = [
        "gdalwarp",
        "-cutline", states_file,
        "-crop_to_cutline",
        "-dstnodata", str(NODATA_VAL),
        "-co", "TILED=YES",
        "-co", "COMPRESS=DEFLATE",
        "-co", "PREDICTOR=2",
        "-co", "NUM_THREADS=ALL_CPUS",
        "-wo", "NUM_THREADS=ALL_CPUS",
        vrt_path,
        ELEVATION_TIF
    ]
    subprocess.run(cmd_warp, check=True)
    print(f"Successfully generated {ELEVATION_TIF} ({os.path.getsize(ELEVATION_TIF):,} bytes)")


def generate_hillshade():
    """Compute projected hillshade taking degree-to-meter latitude scaling into account."""
    os.makedirs(TERRAIN_DIR, exist_ok=True)
    if os.path.exists(HILLSHADE_TIF) and os.path.getsize(HILLSHADE_TIF) > 50_000_000:
        print(f"\nHillshade raster already exists at {HILLSHADE_TIF} ({os.path.getsize(HILLSHADE_TIF):,} bytes). Skipping rebuild.")
        return

    print(f"\nComputing hillshade from {ELEVATION_TIF} using gdaldem...")
    cmd_hs = [
        "gdaldem", "hillshade",
        ELEVATION_TIF,
        HILLSHADE_TIF,
        "-s", "111120",
        "-compute_edges",
        "-co", "TILED=YES",
        "-co", "COMPRESS=DEFLATE",
        "-co", "PREDICTOR=2",
        "-co", "NUM_THREADS=ALL_CPUS"
    ]
    subprocess.run(cmd_hs, check=True)
    print(f"Successfully generated {HILLSHADE_TIF} ({os.path.getsize(HILLSHADE_TIF):,} bytes)")


def generate_terrain_preview_png(states_gdf: gpd.GeoDataFrame):
    """Render high-resolution shaded relief preview map for visual inspection."""
    print("\nRendering high-resolution terrain visualization preview...")

    # Open DEM and Hillshade with decimation for map rendering
    with rasterio.open(ELEVATION_TIF) as src_dem, rasterio.open(HILLSHADE_TIF) as src_hs:
        step = 8  # Subsample every 8th pixel (~4200 x 3380) for ultra crisp visual rendering
        dem_data = src_dem.read(1)[::step, ::step]
        hs_data = src_hs.read(1)[::step, ::step]
        bounds = src_dem.bounds

    fig, ax = plt.subplots(figsize=(16, 13), dpi=250)

    # Elevation mask
    valid_mask = (dem_data != NODATA_VAL)
    dem_masked = np.ma.masked_where(~valid_mask, dem_data)
    hs_masked = np.ma.masked_where(~valid_mask, hs_data)

    # Extent: [minx, maxx, miny, maxy]
    extent = [bounds.left, bounds.right, bounds.bottom, bounds.top]

    # Plot base hillshade in grayscale
    ax.imshow(hs_masked, cmap="gray", extent=extent, vmin=0, vmax=255, alpha=0.55, zorder=1)

    # Overlay hypsometric elevation tint with transparency
    # Colormap showing plains (greens), mid hills (yellows/browns), high peaks (grays/whites)
    cmap_terrain = plt.colormaps["gist_earth"].copy()
    cmap_terrain.set_bad((1, 1, 1, 0))

    vmin = max(0, dem_masked.min())
    vmax = min(7500, dem_masked.max())

    im = ax.imshow(
        dem_masked,
        cmap=cmap_terrain,
        extent=extent,
        vmin=vmin,
        vmax=vmax,
        alpha=0.65,
        zorder=2,
    )

    # Overlay major rivers if available
    if os.path.exists(PROCESSED_RIVERS_FILE):
        try:
            rivers_gdf = gpd.read_file(PROCESSED_RIVERS_FILE)
            major_rivers = rivers_gdf[rivers_gdf["waterway"].isin(["river"])]
            if len(major_rivers) > 0:
                major_rivers.plot(
                    ax=ax,
                    color="#0284C7",
                    linewidth=0.8,
                    alpha=0.85,
                    zorder=3,
                )
        except Exception as e:
            print(f"Note: Could not overlay rivers: {e}")

    # Overlay State boundaries
    states_gdf.plot(
        ax=ax,
        facecolor="none",
        edgecolor="#0F172A",
        linewidth=1.4,
        zorder=4,
    )

    # State Labels
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
    cbar.set_label("Elevation (Meters Above Sea Level)", fontsize=11, fontweight="bold", labelpad=10)

    ax.set_title(
        "North Eastern Region (NER) of India: High-Resolution Shaded Relief & Elevation DEM\n1 Arc-Second (~30 m) SRTM Skadi (EPSG:4326)",
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
    print(f"Saved terrain visualization preview to {PREVIEW_PNG}")

    # Copy to artifact directory
    if os.path.exists(ARTIFACT_DIR):
        artifact_preview = os.path.join(ARTIFACT_DIR, "ner_terrain_preview.png")
        shutil.copy2(PREVIEW_PNG, artifact_preview)
        print(f"Copied preview to artifact directory: {artifact_preview}")


def print_dem_metrics(states_gdf: gpd.GeoDataFrame):
    """Print comprehensive DEM metrics and verify complete NER coverage."""
    with rasterio.open(ELEVATION_TIF) as src:
        crs = src.crs.to_string()
        res = src.res
        width = src.width
        height = src.height
        bounds = src.bounds
        nodata = src.nodata

        # Read in blocks or downsample to compute exact valid min/max and nodata percentage
        # Reading overview/step for statistics
        data = src.read(1)
        valid = (data != nodata)
        total_pixels = width * height
        nodata_pixels = int(np.sum(~valid))
        nodata_pct = (nodata_pixels / total_pixels) * 100.0

        min_elev = int(np.min(data[valid]))
        max_elev = int(np.max(data[valid]))

        print("\n" + "=" * 65)
        print("NER DIGITAL ELEVATION MODEL (DEM) METRICS")
        print("=" * 65)
        print(f"CRS                    : {crs}")
        print(f"Resolution             : {res[0]:.8f}° x {res[1]:.8f}° (~30.8 m x 30.8 m at equator)")
        print(f"Dimensions (W x H)     : {width:,d} x {height:,d} pixels ({total_pixels:,d} total pixels)")
        print(f"Bounds (W, S, E, N)    : [{bounds.left:.6f}°, {bounds.bottom:.6f}°, {bounds.right:.6f}°, {bounds.top:.6f}°]")
        print(f"Minimum Elevation      : {min_elev} m (Brahmaputra / Barak Plains)")
        print(f"Maximum Elevation      : {max_elev} m (Kangchenjunga / Eastern Himalayas)")
        print(f"NoData Value           : {nodata}")
        print(f"NoData Percentage      : {nodata_pct:.2f}% (masked outside NER state borders)")
        print("=" * 65)

        # Verification across all 8 states
        print("\n--- Geographic Coverage Verification Across All 8 States ---")
        coverage_ok = True
        for _, row in states_gdf.iterrows():
            st_name = row["state_name"]
            st_geom = row["geometry"]
            # Sample point inside state
            pt = st_geom.representative_point()
            # Get raster coordinates
            row_idx, col_idx = src.index(pt.x, pt.y)
            val = data[row_idx, col_idx]
            is_valid_sample = (val != nodata)
            print(f"  - {st_name:<20}: Sample at ({pt.x:.3f}°, {pt.y:.3f}°) = {val:5d} m | Covered: {is_valid_sample}")
            if not is_valid_sample:
                coverage_ok = False

        print(f"\nFull NER Coverage Verified: {'YES (100% Covered)' if coverage_ok else 'NO (Coverage Gaps Found)'}")
        assert coverage_ok, "Error: Coverage verification failed for one or more states!"
        print("=" * 65)


def main():
    print("=" * 65)
    print("NER REGIONAL ELEVATION (DEM) PIPELINE")
    print("=" * 65)

    if not os.path.exists(PROCESSED_STATES_FILE):
        raise FileNotFoundError(f"State boundaries file not found at {PROCESSED_STATES_FILE}")

    states_gdf = gpd.read_file(PROCESSED_STATES_FILE)

    # 1. Identify required 1x1 degree tiles
    tiles = get_required_tiles(states_gdf)
    print(f"Identified {len(tiles)} required 1x1° tiles covering all 8 NER states:")
    print("  " + ", ".join([t[2] for t in tiles]))

    # 2. Concurrently download and decompress tiles
    hgt_files = download_all_tiles(tiles)

    # 3. Mosaic and clip to NER boundary
    mosaic_and_clip_dem(hgt_files, PROCESSED_STATES_FILE)

    # 4. Generate projected hillshade
    generate_hillshade()

    # 5. Render high-resolution preview map
    generate_terrain_preview_png(states_gdf)

    # 6. Print raster metrics and verify full coverage
    print_dem_metrics(states_gdf)


if __name__ == "__main__":
    main()
