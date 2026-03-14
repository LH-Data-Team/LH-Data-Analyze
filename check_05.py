import csv
missing = ["다사730463","다사732479","다사750480"]
with open("output/05_격자별_EPDO_인프라통합.csv", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    print("컬럼:", reader.fieldnames)
    print("컬럼수:", len(reader.fieldnames))
    for r in reader:
        if r["grid_gid"] in missing:
            print(f"\n--- {r['grid_gid']} ---")
            for k, v in r.items():
                print(f"  {k} = {v}")
