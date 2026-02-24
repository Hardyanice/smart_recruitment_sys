import os
import json
import re
import numpy as np
from dotenv import load_dotenv
import cohere

from google.adk import Agent

# changed by souhardya on 10/2/26 13:00

#from .sub_agents.gaze_evaluator_agent.tools import load_latest_gaze_summary
from .tools import load_latest_gaze_summary


# =========================
# ENV SETUP
# =========================
load_dotenv()

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
if not COHERE_API_KEY:
    raise RuntimeError("COHERE_API_KEY not found in environment")

co = cohere.ClientV2(api_key=COHERE_API_KEY)


# =========================
# PATH SETUP
# =========================
BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)


# =========================
# JSON SAFETY HELPERS
# =========================
def make_json_safe(obj):
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    else:
        return obj


def extract_json(text: str):
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(match.group())


# =========================
# PROMPT
# =========================
SYSTEM_PROMPT = """
You are an automated exam proctoring decision agent.

You analyze structured gaze-behavior evidence derived from a video proctoring system.

Definitions:
- LONG_STREAK: sustained off-screen gaze, strong indicator of intent
- REPEATED_GLANCES: multiple short but consistent off-screen glances
- LEFT/RIGHT: likely off-screen material
- DOWN: likely desk-level material

Rules:
- Occasional short glances are normal
- Repeated or sustained gaze in the same direction indicates intent
- Higher percentage of suspicious time increases confidence
- Your decision must be conservative but firm when patterns exist

Output STRICT JSON only in this format:
{
  "verdict": "CHEATED | SUSPICIOUS | NOT_CHEATED",
  "confidence": 0.0,
  "reasons": [string],
  "recommended_action": string
}
"""


# =========================
# AGENT
# =========================
class GazeDecisionAgent(Agent):
    def __init__(self):
        super().__init__(
            name="gaze_decision_agent",
            description="LLM-based gaze cheating decision agent using CV-derived evidence"
        )
#-------------------------------------------------------------------------------
    def run(self, context: dict = None):
        """
        Loads the gaze summary JSON for the current session and reasons over it.
        """

        '''if not context or "session_id" not in context:
            raise ValueError("session_id missing in gaze agent context")

        session_id = context["session_id"]
'''
        # Now loads the correct session-bound summary
        gaze_data = load_latest_gaze_summary(BASE_DIR)

        events = gaze_data.get("events", [])

        evidence = {
            "exam_duration_sec": gaze_data.get("exam_duration_sec"),
            "suspicious_time_sec": gaze_data.get("suspicious_time_sec"),
            "suspicious_time_percentage": gaze_data.get("suspicious_time_percentage"),
            "total_suspicious_events": gaze_data.get("total_events", len(events)),
            "events": events
        }

        evidence = make_json_safe(evidence)

        # --- DEBUG ---
        print("\n[DEBUG] Evidence sent to gaze LLM:")
        print(json.dumps(evidence, indent=2))

        response = co.chat(
            model="command-a-03-2025",
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": [{"type": "text", "text": SYSTEM_PROMPT}]
                },
                {
                    "role": "user",
                    "content": [{
                        "type": "text",
                        "text": f"""
    EVIDENCE SUMMARY (JSON):
    {json.dumps(evidence, indent=2)}

    Analyze the evidence and determine whether the candidate cheated.
    Return STRICT JSON only.
    """
                    }]
                }
            ]
        )

        raw_text = response.message.content[0].text
        decision = extract_json(raw_text)

        return decision


#-------------------------------------------------------------------------------
'''    
    def run(self, context: dict = None):
        """
        Loads the latest gaze summary JSON and reasons over it.
        """

        gaze_data = load_latest_gaze_summary(BASE_DIR)

        # ✅ FIXED: map to actual analyzer schema
        events = gaze_data.get("events", [])

        evidence = {
            "exam_duration_sec": gaze_data.get("exam_duration_sec"),
            "suspicious_time_sec": gaze_data.get("suspicious_time_sec"),
            "suspicious_time_percentage": gaze_data.get("suspicious_time_percentage"),
            "total_suspicious_events": gaze_data.get("total_events", len(events)),
            "events": events
        }

        evidence = make_json_safe(evidence)

        # --- DEBUG SAFETY (optional, leave in) ---
        print("\n[DEBUG] Evidence sent to gaze LLM:")
        print(json.dumps(evidence, indent=2))

        response = co.chat(
            model="command-a-03-2025",
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": SYSTEM_PROMPT
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""
EVIDENCE SUMMARY (JSON):
{json.dumps(evidence, indent=2)}

Analyze the evidence and determine whether the candidate cheated.
Return STRICT JSON only.
"""
                        }
                    ]
                }
            ]
        )

        raw_text = response.message.content[0].text
        decision = extract_json(raw_text)

        return decision

'''
# =========================
# LOCAL TEST
# =========================
if __name__ == "__main__":
    agent = GazeDecisionAgent()
    print("[DEBUG] GazeDecisionAgent.run() called")

    # changed as well by souhardya on 10/2/26 16:35 to pass session_id for loading correct summary
    output = agent.run({
    "session_id": "TEST_SESSION"
    })

    print("\n--- GAZE AGENT DECISION ---")
    print(json.dumps(output, indent=2))
