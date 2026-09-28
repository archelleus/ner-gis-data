# Contributing to the NER GIS Project

We welcome contributions from GIS researchers, cartographers, software engineers, and hackathon participants! This guide explains how you can contribute to improving and expanding open geospatial data for Northeast India.

---

## Areas Where Contributions Are Needed

1. **New Spatial Layers**:
   - Railway lines and train stations across Assam and Tripura
   - Protected wildlife reserves, National Parks, and sanctuaries (Kaziranga, Manas, Namdapha, etc.)
   - Hospital and primary healthcare center (PHC) points
   - Landslide vulnerability inventory and historical flood hazard zones
2. **Boundary Updates**:
   - Updating newly created districts in Assam (e.g., Tamulpur, Bajali) or Arunachal Pradesh
3. **Pipeline & Web Improvements**:
   - Adding 3D terrain rendering in MapLibre via custom DEM raster terrain
   - Extending ML features in `ner_ml_package`
   - Adding automated GitHub Actions CI/CD to run `validate_ner_project.py`

---

## Development Workflow

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/<your-username>/ner-gis-data.git
cd ner-gis-data

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install geopandas rasterio shapely matplotlib requests pmtiles pandas
```

### 2. Making Layer Modifications

- Keep raw queries or extraction scripts in `scripts/`.
- Ensure all vector layers are saved in **WGS 84 (`EPSG:4326`)** format.
- Run `shapely.validation.make_valid` on all geometries to prevent topology errors.

### 3. Run Validation Suite

Before opening a pull request, run the comprehensive project validator:

```bash
python3 scripts/validate_ner_project.py
```

Ensure that:
- All states and districts pass validation
- Geometries have 0 self-intersections or invalid nodes
- Web previews and metadata dictionaries are properly updated

### 4. Submitting a Pull Request

1. Fork the repository and create your branch (`git checkout -b feature/railway-layer`).
2. Commit your changes with clear messages (`git commit -m "Add NER railway network layer"`).
3. Push to your branch and open a Pull Request.
4. Describe the data sources and ensure they conform to open-source licenses (ODbL, CC BY, or Public Domain).
