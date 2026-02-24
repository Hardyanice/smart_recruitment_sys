import json
import os


def load_keystroke_log(base_dir, user_id):
    """
    Load keystroke JSON produced by root agent.
    """
    path = os.path.join(
        base_dir,
        "proctoring_logs",
        "keystroke",
        f"keystroke_sess_{user_id}.json"
    )

    if not os.path.exists(path):
        raise FileNotFoundError(f"Keystroke log not found: {path}")

    with open(path, "r") as f:
        return json.load(f)


def load_gaze_verdict(base_dir, user_id):
    """
    Load gaze LLM verdict JSON.
    """
    path = os.path.join(
        base_dir,
        "proctoring_logs",
        "gaze_verdicts",
        f"gaze_verdict_sess_{user_id}.json"
    )

    if not os.path.exists(path):
        raise FileNotFoundError(f"Gaze verdict not found: {path}")

    with open(path, "r") as f:
        return json.load(f)
