# Data Licensing & Attributions

This repository provides open-access spatial data for the **North Eastern Region (NER) of India**. The datasets contained herein are compiled, clipped, validated, and derived from multiple authoritative open-data sources. Each source retains its respective license as outlined below.

---

## 1. Layer-by-Layer Licensing Matrix

| Layer / Asset | Origin / Source | Upstream License | Attribution Notice |
| :--- | :--- | :--- | :--- |
| **Roads (`ner_roads.geojson`)** | [OpenStreetMap](https://www.openstreetmap.org/) | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/) | © OpenStreetMap contributors |
| **Rivers (`ner_rivers.geojson`)** | [OpenStreetMap](https://www.openstreetmap.org/) | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/) | © OpenStreetMap contributors |
| **Settlements (`ner_settlements.geojson`)** | [OpenStreetMap](https://www.openstreetmap.org/) | [ODbL 1.0](https://opendatacommons.org/licenses/odbl/) | © OpenStreetMap contributors |
| **States (`ner_states.geojson`)** | [geoBoundaries v6 ADM1](https://www.geoboundaries.org/) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | geoBoundaries / Runfola et al. (2020) |
| **Districts (`ner_districts.geojson`)** | [geoBoundaries v6 ADM2](https://www.geoboundaries.org/) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | geoBoundaries / Runfola et al. (2020) |
| **Elevation DEM (`ner_elevation.tif`)** | [NASA SRTM Skadi 30m / USGS](https://portal.opentopography.org/) | Public Domain / Open Access | NASA / USGS / OpenTopography |
| **Hillshade & Slope (`ner_hillshade`, `ner_slope`)** | Derived from NASA SRTM 30m | Public Domain / CC BY 4.0 | Processed via GDAL / RichDEM |
| **PMTiles Archive (`ner_map.pmtiles`)** | Multi-layer composite of above | ODbL 1.0 & CC BY 4.0 | © OpenStreetMap contributors & geoBoundaries |
| **ML Engineered Features (`ner_ml_package`)** | Spatial joins of above | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | NER GIS Project Contributors |

---

## 2. Open Database License (ODbL 1.0) Summary
The OpenStreetMap data (roads, rivers, settlements) is made available under the Open Database License: [http://opendatacommons.org/licenses/odbl/1.0/](http://opendatacommons.org/licenses/odbl/1.0/). Any rights in individual contents of the database are licensed under the Database Contents License: [http://opendatacommons.org/licenses/dbcl/1.0/](http://opendatacommons.org/licenses/dbcl/1.0/).

**Your Rights**:
- You are free to copy, distribute, transmit, and adapt the data.
- Any adaptation or derivative database must also be released under the ODbL if made publicly available.
- You must attribute OpenStreetMap using: `© OpenStreetMap contributors`.

---

## 3. Creative Commons Attribution 4.0 (CC BY 4.0) Summary
The administrative boundaries are derived from the geoBoundaries database ([https://www.geoboundaries.org](https://www.geoboundaries.org)):
> Runfola, D. et al. (2020) "geoBoundaries: A global database of political administrative boundaries." *PLOS ONE* 15(4): e0231866. [doi:10.1371/journal.pone.0231866](https://doi.org/10.1371/journal.pone.0231866).

---

## 4. Academic, Educational & Hackathon Boundary Disclaimer

> **DISCLAIMER**: 
> The administrative and political boundaries provided in this repository are sourced from global open community datasets (OpenStreetMap and geoBoundaries) solely for academic research, education, computational modeling, and hackathon prototypes (e.g., Smart India Hackathon). 
> They do **not** represent official, legal, or political boundary demarcations endorsed by the Government of India or the Survey of India. For official legal demarcations, please refer directly to the Survey of India ([https://surveyofindia.gov.in](https://surveyofindia.gov.in)).
