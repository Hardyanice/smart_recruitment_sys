import json
import os

# changed by souhardya on 10/2 16:36 for loading specific session gaze summary

def load_latest_gaze_summary(base_dir):
    summary_dir = os.path.join(base_dir, "proctoring_logs", "gaze_summaries")

    if not os.path.exists(summary_dir):
        raise FileNotFoundError(
            f"Gaze summary directory does not exist: {summary_dir}"
        )

    files = [
        os.path.join(summary_dir, f)
        for f in os.listdir(summary_dir)
        if f.endswith(".json")
    ]

    if not files:
        raise FileNotFoundError("No gaze summary JSON files found")

    latest = max(files, key=os.path.getmtime)

    with open(latest, "r") as f:
        return json.load(f)


# Changed by souhardya on 10/2 16:23 for loading specific session gaze summary

'''def load_latest_gaze_summary(base_dir: str, session_id: str):
    """
    Load gaze summary JSON for a specific assessment session.
    """

    summary_dir = os.path.join(base_dir, "proctoring_logs", "gaze_summaries")

    if not os.path.exists(summary_dir):
        raise FileNotFoundError(
            f"Gaze summary directory does not exist: {summary_dir}"
        )

    # Expected filename pattern
    expected_name = f"gaze_summary_{session_id}.json"
    summary_path = os.path.join(summary_dir, expected_name)

    if not os.path.exists(summary_path):
        raise FileNotFoundError(
            f"Gaze summary for session '{session_id}' not found: {summary_path}"
        )

    with open(summary_path, "r") as f:
        return json.load(f)
'''