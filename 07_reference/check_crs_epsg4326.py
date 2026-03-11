from __future__ import annotations

from pathlib import Path

import geopandas as gpd


ROOT = Path(__file__).resolve().parents[1]
TARGET_EPSG = "EPSG:4326"


def main() -> None:
    files = sorted(list(ROOT.rglob("*.geojson")) + list(ROOT.rglob("*.shp")))
    if not files:
        print("No GIS files found (.geojson/.shp).")
        return

    print(f"Checking {len(files)} GIS files against {TARGET_EPSG}")
    invalid = []

    for p in files:
        try:
            gdf = gpd.read_file(p)
            crs = str(gdf.crs) if gdf.crs is not None else "None"
            ok = crs.upper() == TARGET_EPSG
            rel = p.relative_to(ROOT)
            print(f"[{'OK' if ok else 'NG'}] {rel} :: {crs}")
            if not ok:
                invalid.append((rel, crs))
        except Exception as e:
            rel = p.relative_to(ROOT)
            print(f"[ERR] {rel} :: {e}")
            invalid.append((rel, "READ_ERROR"))

    print("-" * 60)
    if invalid:
        print("Files needing action:")
        for rel, crs in invalid:
            print(f"- {rel} ({crs})")
        raise SystemExit(1)

    print("All checked GIS files are EPSG:4326.")


if __name__ == "__main__":
    main()
