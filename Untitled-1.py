import pandas as pd

df = pd.read_csv("08_link_master_base_plus13_acc.csv")

df_sorted = df.sort_values("acc_cnt", ascending=True)
df_sorted.to_csv("08_link_master_base_plus13_acc_sorted_asc.csv", index=False, encoding="utf-8-sig")

print("saved: 08_link_master_base_plus13_acc_sorted_asc.csv")
print(df_sorted[["v_link_id", "link_id", "dir", "acc_cnt"]].head(20))