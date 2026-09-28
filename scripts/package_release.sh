#!/usr/bin/env bash
# ==============================================================================
# Helper script to package distribution archives for GitHub Releases
# ==============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "=== Packaging NER GIS & ML Release Bundles ==="

# 1. Package GIS Bundle
echo "[1/2] Creating ner_gis_package.zip..."
rm -rf /tmp/ner_gis_package ner_gis_package.zip
mkdir -p /tmp/ner_gis_package/data /tmp/ner_gis_package/web_tiles

cp README_FRONTEND.md /tmp/ner_gis_package/README.md
cp web/DATA_DICTIONARY.md /tmp/ner_gis_package/DATA_DICTIONARY.md
cp web/ner_final_preview.png /tmp/ner_gis_package/
cp data/processed/*.geojson /tmp/ner_gis_package/data/
cp web/ner_map.pmtiles /tmp/ner_gis_package/web_tiles/
cp web/hillshade_overlay.png /tmp/ner_gis_package/web_tiles/
cp web/slope_overlay.png /tmp/ner_gis_package/web_tiles/
cp web/layer_config.json /tmp/ner_gis_package/web_tiles/

(cd /tmp && zip -r -9 "${ROOT_DIR}/ner_gis_package.zip" ner_gis_package)
rm -rf /tmp/ner_gis_package
echo "  -> Created ner_gis_package.zip ($(du -h "${ROOT_DIR}/ner_gis_package.zip" | cut -f1))"

# 2. Package ML Bundle
echo "[2/2] Creating ner_ml_package.zip..."
rm -f ner_ml_package.zip
zip -r -9 ner_ml_package.zip ner_ml_package -x "ner_ml_package/__pycache__/*"
echo "  -> Created ner_ml_package.zip ($(du -h "${ROOT_DIR}/ner_ml_package.zip" | cut -f1))"

echo "=== Packaging Complete! Ready for GitHub Releases ==="
