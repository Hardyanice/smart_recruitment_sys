import pandas as pd
from src.agent.resume_screening_agent import screen_resume

# Load data
resumes = pd.read_csv("data/raw/Resume.csv")
jds = pd.read_csv("data/raw/job_title_des.csv")

JD_ID = 181
jd_text = jds.iloc[JD_ID]["Job Description"]

results = []

for idx, row in resumes.iterrows():
    resume_text = row["Resume_str"]

    output = screen_resume(resume_text, jd_text)

    results.append({
        "resume_id": idx,
        "score": output.get("score", 0),
        "coverage": output.get("coverage", None),   # safe access
        "decision": output.get("decision", "Unknown")
    })

df = pd.DataFrame(results).sort_values("score", ascending=False)

df.to_csv("screened_candidates.csv", index=False)

print(df.head())
