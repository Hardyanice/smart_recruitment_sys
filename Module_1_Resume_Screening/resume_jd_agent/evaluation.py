import pandas as pd

df = pd.read_csv("screened_candidates.csv")

# Coverage-based relevance
df["relevant"] = df["coverage"] >= 0.3

def precision_at_k(df, k=5):
    top_k = df.sort_values("score", ascending=False).head(k)
    return top_k["relevant"].sum() / k

print("Precision@5 :", precision_at_k(df, 5))
print("Precision@10:", precision_at_k(df, 10))

print("\nScore Statistics")
print(df["score"].describe())
