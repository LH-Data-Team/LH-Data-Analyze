# QGIS Packaging Guide

## Required files

- `project.qgz` (or `project.qgs`)
- Style files `*.qml`
- All referenced layers (SHP/GeoJSON/CSV) used in the project

## Required settings

1. Project CRS: `EPSG:4326`
2. Save paths as **Relative**
   - QGIS menu: `Project > Properties > General > Save paths = Relative`
3. Verify no broken layers when project is reopened

## Recommended structure

```text
03_visualization_qgis/
  project.qgz
  styles/
    roads.qml
    grids.qml
  layers/
    roads.shp
    roads.shx
    roads.dbf
    roads.prj
    grids.geojson
```

## Final check

- Open the project from this folder only
- Confirm all layers load without extra path changes
