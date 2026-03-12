import geopandas as gpd
import pandas as pd
from pathlib import Path

root = Path(r"c:/Users/jch23/OneDrive/바탕 화면/SBJ_2601_001")
grid = root / "data" / "01._격자_(4개_시·구).geojson"
risk = root / "epdo_analysis" / "output" / "08_격자_종합위험지수.csv"
out_geo = root / "02_data_analysis" / "grid_risk_joined.geojson"
out_shp = root / "02_data_analysis" / "grid_risk_joined.shp"

gdf = gpd.read_file(grid)
df = pd.read_csv(risk, encoding="utf-8-sig", low_memory=False)

gdf["gid"] = gdf["gid"].astype(str)
df["grid_gid"] = df["grid_gid"].astype(str)

out = gdf.merge(df, left_on="gid", right_on="grid_gid", how="left")
out = out.to_crs("EPSG:4326")

out.to_file(out_geo, driver="GeoJSON")
out.to_file(out_shp, driver="ESRI Shapefile", encoding="utf-8")

print("saved:", out_geo)
print("saved:", out_shp)
