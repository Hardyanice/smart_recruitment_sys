import pandas as pd

def load_resume_by_id(path, resume_id):
    df = pd.read_csv(path)
    return str(df.iloc[resume_id]["Resume_str"]).lower()

def load_jd_by_id(path, jd_id):
    df = pd.read_csv(path)
    return str(df.iloc[jd_id]["Job Description"]).lower()
