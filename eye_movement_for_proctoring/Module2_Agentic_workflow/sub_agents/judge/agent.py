# Module2_Agentic_workflow/sub_agents/combined_verdict_agent/agent.py

import os
import json
import re
from datetime import datetime
import cohere
from dotenv import load_dotenv

load_dotenv()

COHERE_API_KEY = os.getenv("COHERE_API_KEY")
if not COHERE_API_KEY:
    raise RuntimeError("COHERE_API_KEY missing")

co = cohere.ClientV2(api_key=COHERE_API_KEY)


SYSTEM_PROMPT = """
You are the final integrity and hiring adjudication authority.

You are given:
1. Whether the technical question was missing
2. Gaze integrity verdict
3. Keystroke behavioral integrity summary
4. Technical evaluation score (if available)

CRITICAL RULE:

If question_missing == true:
- You must IGNORE technical_score completely.
- You must base decision ONLY on integrity systems.
- Final decision must be:
  CHEATED | NOT_CHEATED | SUSPICIOUS
- You must clearly state that question was unavailable.

If question_missing == false:
- Combine integrity + technical performance.
- Final decision must be:
  PASS_TO_NEXT_ROUND | DO_NOT_PASS | REVIEW_MANUALLY | CHEATED | SUSPICIOUS

General Rules:

1. If strong cheating evidence → CHEATED.
2. If integrity clean but technical score is 0 or invalid → DO_NOT_PASS.
3. If integrity clean and technical acceptable → PASS_TO_NEXT_ROUND.
4. Mixed signals → REVIEW_MANUALLY.
5. Borderline integrity → SUSPICIOUS.

Return STRICT JSON only:

{
  "final_decision": "...",
  "confidence": 0.0,
  "reasons": [string],
  "recommended_action": string
}
"""


def extract_json(text: str):
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON found in LLM output")
    return json.loads(match.group())


class CombinedVerdictAgent:
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def run(self, session_id):

        # ---------------- LOAD FILES ----------------

        gaze_path = os.path.join(
            self.base_dir,
            "proctoring_logs",
            "gaze_verdicts",
            f"gaze_verdict_{session_id}.json"
        )

        keystroke_dir = os.path.join(
            self.base_dir,
            "proctoring_logs",
            "keystroke"
        )

        if not os.path.exists(gaze_path):
            raise FileNotFoundError("Gaze verdict not found")

        keystroke_files = [
            os.path.join(keystroke_dir, f)
            for f in os.listdir(keystroke_dir)
            if f.endswith(".json")
        ]

        if not keystroke_files:
            raise FileNotFoundError("No keystroke logs found")

        keystroke_path = max(keystroke_files, key=os.path.getmtime)

        with open(gaze_path) as f:
            gaze = json.load(f)

        with open(keystroke_path) as f:
            keystroke = json.load(f)

        # ---------------- EXTRACT DATA ----------------

        assessment_entries = keystroke.get("assessment_data", [])

        max_prob = 0.0
        total_switches = 0
        paste_events = 0
        technical_score = 0
        question_missing = False

        for entry in assessment_entries:

            integrity = entry.get("integrity", {})
            max_prob = max(max_prob, integrity.get("prob", 0.0))
            total_switches += integrity.get("switches", 0)
            paste_events += integrity.get("paste_count", 0)

            # Question validity check
            if not entry.get("question"):
                question_missing = True

            # Extract technical score safely
            try:
                eval_response = entry.get("eval_response", "{}")
                parsed = json.loads(eval_response)
                technical_score = max(
                    technical_score,
                    parsed.get("score", 0)
                )
            except Exception:
                pass

        integrity_summary = {
            "max_prob": max_prob,
            "total_switches": total_switches,
            "paste_events": paste_events
        }

        evidence = {
            "question_missing": question_missing,
            "technical_score": technical_score,
            "gaze_verdict": gaze,
            "keystroke_summary": integrity_summary
        }

        # ---------------- LLM CALL ----------------

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
COMBINED ASSESSMENT EVIDENCE (JSON):
{json.dumps(evidence, indent=2)}

Determine the final decision.
Return STRICT JSON only.
"""
                    }]
                }
            ]
        )

        raw = response.message.content[0].text
        decision = extract_json(raw)

        # ---------------- SAVE OUTPUT ----------------

        out_dir = os.path.join(
            self.base_dir,
            "proctoring_logs",
            "final_verdicts"
        )
        os.makedirs(out_dir, exist_ok=True)

        out_path = os.path.join(
            out_dir,
            f"final_verdict_{session_id}.json"
        )

        decision["generated_at"] = datetime.now().isoformat()
        decision["supporting_evidence"] = evidence

        with open(out_path, "w") as f:
            json.dump(decision, f, indent=2)

        print(f"[FINAL] Verdict saved → {out_path}")

        return decision
