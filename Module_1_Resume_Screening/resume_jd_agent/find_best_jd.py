import pandas as pd
from src.agent.resume_jd_agent import screen_resume

# Load data
resumes = pd.read_csv("data/raw/Resume.csv")
jds = pd.read_csv("data/raw/job_title_des.csv")

# Use a subset of resumes for speed
resume_sample = resumes.sample(50, random_state=42)

jd_scores = []

for jd_idx, jd_row in jds.iterrows():
    jd_text = jd_row["Job Description"]

    scores = []

    for _, res_row in resume_sample.iterrows():
        resume_text = res_row["Resume_str"]
        out = screen_resume(resume_text, jd_text)
        scores.append(out["final_score"])

    jd_scores.append({
        "jd_id": jd_idx,
        "job_title": jd_row.get("Job Title", "N/A"),
        "max_score": max(scores),
        "avg_top5": sum(sorted(scores, reverse=True)[:5]) / 5
    })

# Rank JDs
df = pd.DataFrame(jd_scores).sort_values("avg_top5", ascending=False)

df.to_csv("best_jd_candidates.csv", index=False)
print(df.head(10))
