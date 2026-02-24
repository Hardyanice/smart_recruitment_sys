"""
Gaze Analyzer
Consumes gaze CSV and produces session-level summary JSON
"""

import pandas as pd
import os
import json
from collections import Counter
from datetime import datetime

#--------inclduing project root inside sys.path to avoid import issues by souhardya 10/2 17:31
import sys
import os

EYE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if EYE_ROOT not in sys.path:
    sys.path.insert(0, EYE_ROOT)

#---------------------------------------------------------------

# =========================
# CONFIG
# =========================
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--session_id", required=True)
args = parser.parse_args()

SESSION_ID = args.session_id


#USER_ID = "USER_2026"

LONG_STREAK_FRAMES = 45
MIN_EVENT_FRAMES = 10
MAX_EVENT_FRAMES = 35
ACCUMULATED_FRAMES_THRESHOLD = 75

CHEAT_DIRECTIONS = {"LEFT", "RIGHT", "DOWN"}

# =========================
# PATHS
# =========================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GAZE_DIR = os.path.join(BASE_DIR, "proctoring_logs", "gaze")
SUMMARY_DIR = os.path.join(BASE_DIR, "proctoring_logs", "gaze_summaries")

os.makedirs(SUMMARY_DIR, exist_ok=True)

CSV_PATH = os.path.join(GAZE_DIR, f"gaze_{SESSION_ID}.csv")
SUMMARY_PATH = os.path.join(
    SUMMARY_DIR,
    f"gaze_summary_{SESSION_ID}.json"
)

# overwrite summary every run
if os.path.exists(SUMMARY_PATH):
    os.remove(SUMMARY_PATH)

# =========================
# HELPERS
# =========================
def to_seconds(t):
    h, m, s = map(int, t.split(":"))
    return h * 3600 + m * 60 + s

def dominant_direction(dirs):
    c = Counter(dirs)
    dom, count = c.most_common(1)[0]
    return dom, count / len(dirs)

# =========================
# ANALYSIS
# =========================
if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(f"No gaze CSV found: {CSV_PATH}")

df = pd.read_csv(CSV_PATH)
df["time_sec"] = df["timestamp"].apply(to_seconds)

instances = []
used_frames = set()
n = len(df)

i = 0
while i < n:
    row = df.iloc[i]
    if row.face_detected and not row.looking_at_screen and row.direction in CHEAT_DIRECTIONS:
        start = i
        dirs = []
        while (
            i < n
            and df.iloc[i].face_detected
            and not df.iloc[i].looking_at_screen
            and df.iloc[i].direction in CHEAT_DIRECTIONS
        ):
            dirs.append(df.iloc[i].direction)
            i += 1

        length = i - start
        dom, consistency = dominant_direction(dirs)

        if length >= LONG_STREAK_FRAMES and consistency >= 0.7:
            instances.append({
                "start_frame": start,
                "end_frame": i - 1,
                "start_time": df.iloc[start].timestamp,
                "end_time": df.iloc[i - 1].timestamp,
                "duration_sec": int(df.iloc[i - 1].time_sec - df.iloc[start].time_sec),
                "event_type": "LONG_STREAK",
                "direction": dom,
                "consistency": round(consistency, 2)
            })
            used_frames.update(range(start, i))
    else:
        i += 1

total_time = int(df["time_sec"].iloc[-1] - df["time_sec"].iloc[0])
suspicious_time = sum(e["duration_sec"] for e in instances)
suspicious_percentage = round((suspicious_time / total_time) * 100, 2) if total_time else 0

summary = {
    "exam_duration_sec": total_time,
    "suspicious_time_sec": suspicious_time,
    "suspicious_time_percentage": suspicious_percentage,
    "total_events": len(instances),
    "events": instances,
    "generated_at": datetime.now().isoformat()
}

with open(SUMMARY_PATH, "w") as f:
    json.dump(summary, f, indent=2)

print(f"[GAZE] Summary saved → {SUMMARY_PATH}")


# gaze agent activation added by souhardya on 10/2 17:20 to trigger gaze agent after summary generation

# =========================
# RUN GAZE DECISION AGENT
# =========================

print("[GAZE] Running gaze decision agent...")

# Import here to avoid circular / path issues
from Module2_Agentic_workflow.sub_agents.gaze_evaluator_agent.agent import GazeDecisionAgent

agent = GazeDecisionAgent()

try:
    verdict = agent.run({})

    VERDICT_DIR = os.path.join(BASE_DIR, "proctoring_logs", "gaze_verdicts")
    os.makedirs(VERDICT_DIR, exist_ok=True)

    VERDICT_PATH = os.path.join(
        VERDICT_DIR,
        f"gaze_verdict_{SESSION_ID}.json"
    )

    with open(VERDICT_PATH, "w") as f:
        json.dump(verdict, f, indent=2)

    print(f"[GAZE] Verdict saved → {VERDICT_PATH}")

except Exception as e:
    print(f"[GAZE] ERROR while running gaze decision agent: {e}")



# =========================
# RUN JUDGE AGENT
# =========================

from Module2_Agentic_workflow.sub_agents.judge.agent import CombinedVerdictAgent

final_agent = CombinedVerdictAgent(BASE_DIR)
final_agent.run(SESSION_ID)
