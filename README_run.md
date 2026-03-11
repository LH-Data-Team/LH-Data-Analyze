# Run Guide (UTF-8, EPSG:4326)

This file defines reproducible execution order for submission.

## 1) Environment setup

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 2) Encoding policy

- Python source/comments: UTF-8
- CSV output: use `encoding="utf-8-sig"` where possible

## 3) Analysis pipeline order

Run from repository root:

```bash
python epdo_analysis/scripts/01_epdo_score.py
python epdo_analysis/scripts/02_link_traffic.py
python epdo_analysis/scripts/03_link_epdo_risk.py
python epdo_analysis/scripts/04_cause_analysis.py
python epdo_analysis/scripts/05_grid_epdo_infra.py
python epdo_analysis/scripts/06_infra_analysis.py
python epdo_analysis/scripts/07_link_speed_congestion.py
python epdo_analysis/scripts/08_grid_composite_risk.py
python epdo_analysis/scripts/09_entropy_weight.py
python epdo_analysis/scripts/10_nb_regression_weight.py
python epdo_analysis/scripts/07_ml_risk_model.py
```

## 4) Output locations

- Main outputs: `epdo_analysis/output/`
- Additional GIS outputs: `output/`

## 5) CRS requirement (EPSG:4326)

All submitted SHP/GeoJSON must use WGS84 (`EPSG:4326`).

Run CRS checker before packaging:

```bash
python 07_reference/check_crs_epsg4326.py
```

If any file is not EPSG:4326, reproject it in QGIS and save again.

## 6) QGIS requirement

- Include project file: `.qgz` or `.qgs`
- Save layer paths as **relative**
- Set project CRS to `EPSG:4326`
- Include used style files `.qml`

See `03_visualization_qgis/README_qgis_project.md` for packaging details.
