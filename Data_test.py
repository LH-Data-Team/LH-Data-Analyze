import pandas as pd

df = pd.read_csv("07._주중주말_서비스인구.csv")

# 북(위) → 남(아래), 서(왼쪽) → 동(오른쪽)
df_sorted = df.sort_values(
    by=["lat", "lon"],
    ascending=[False, True]
)

df_sorted.head()
