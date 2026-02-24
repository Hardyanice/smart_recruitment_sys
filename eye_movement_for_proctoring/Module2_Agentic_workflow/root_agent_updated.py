import asyncio
import json
import datetime
from pathlib import Path
import os
from dotenv import load_dotenv
import time
import pandas as pd
import numpy as np
import json
from datetime import datetime
import joblib

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .sub_agents.question_agent.agent import question_agent
from .sub_agents.evaluator_agent.agent import evaluator_agent
from .sub_agents.gaze_evaluator_agent.agent import GazeDecisionAgent

# Setting path
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), "sub_agents", "question_agent", ".env")
load_dotenv(dotenv_path)

# Load the model once when the agent script is initialized
INTEGRITY_MODEL_PATH = PROJECT_ROOT / "Module2_Agentic_workflow" / "model" / "gradient_boosting_integrity_model_new.pkl"
INTEGRITY_MODEL = joblib.load(INTEGRITY_MODEL_PATH)

# Defining RootAgentClass
class RecruitmentRootAgent:
    def __init__(self, candidate_id: str, job_desc="Standard Technical JD"):
        self.app_name = "RecruitmentApp"
        self.user_id = candidate_id
        self.job_desc = job_desc
        self.session_id = f"sess_{candidate_id}"

        self.service = InMemorySessionService()
        self.log_dir = PROJECT_ROOT / "proctoring_logs" / "keystroke"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.max_questions = 1

        asyncio.run(self._bootstrap_session())

        self.q_runner = Runner(agent=question_agent, app_name=self.app_name, session_service=self.service)
        self.e_runner = Runner(agent=evaluator_agent, app_name=self.app_name, session_service=self.service)
        self.gaze_agent = GazeDecisionAgent()

    async def _bootstrap_session(self):
        await self.service.create_session(
            app_name=self.app_name,
            user_id=self.user_id,
            session_id=self.session_id,
            state={
                "status": "started",
                "question_count": 0,
                "last_question_text": "",
                "question_wise_logs": [],
            },
        )

    # works
    # def get_next_question(self):
    # # No more session fetching or tool calling here
    #     start_time = time.perf_counter()
    #     prompt = f"Using this Job Description: {self.job_desc}\n\nGenerate the next one-sentence technical question."

    #     query = types.Content(role="user", parts=[types.Part(text=prompt)])
    #     events = self.q_runner.run(
    #         user_id=self.user_id,
    #         session_id=self.session_id,
    #         new_message=query,
    #     )

    #     question_text = ""
    #     for event in events:
    #         if event.is_final_response():
    #             question_text = event.content.parts[0].text

    #     print(f"[DEBUG] Question Gen took: {time.perf_counter() - start_time:.4f}s")
    #     return question_text

    

    def get_next_question(self):
        prompt = f"Using this Job Description: {self.job_desc}\n\nGenerate the next one-sentence technical question."
        query = types.Content(role="user", parts=[types.Part(text=prompt)])
        
        start_time = time.perf_counter()
        first_token_time = None
        question_text = ""

        # Start the runner stream
        events = self.q_runner.run(
            user_id=self.user_id,
            session_id=self.session_id,
            new_message=query,
        )

        for event in events:
            # Capture the moment the model starts "talking"
            if first_token_time is None:
                first_token_time = time.perf_counter()
                ttft = first_token_time - start_time
                print(f"\n[TIMER] Time to First Token (Thinking): {ttft:.4f}s")

            if event.is_final_response():
                question_text = event.content.parts[0].text

        end_time = time.perf_counter()
        total_time = end_time - start_time
        generation_time = end_time - (first_token_time or start_time)

        print(f"[TIMER] Generation Time (Writing): {generation_time:.4f}s")
        print(f"[TIMER] TOTAL DELAY: {total_time:.4f}s")
        print("-" * 30)
        
        return question_text

    def run_integrity_model(self, integrity_data):
        # Ensure these lists are populated from the updated JavaScript
        ikl_times = integrity_data.get('ikl_times', [])
        hold_times = integrity_data.get('hold_times', [])
        backspace_count = integrity_data.get('backspace_count', 0)
        mouse_clicks = integrity_data.get('mouse_click_count', 0)
        total_keys = len(integrity_data.get('ikl_times', []))

        # Calculate the real ratio
        # Use max(1, total_keys) to avoid division by zero
        mouse_ratio = mouse_clicks / max(1, total_keys)
        # Validation: Tkinter used a 50-event limit
        if len(ikl_times) < 50:
            return {"prob": 0.0, "is_flagged": False, "reason": "Insufficient data"}

        # Feature Engineering - MUST MATCH TKINTER NAMES EXACTLY
        features = pd.DataFrame([{
            "Avg_HoldTime": np.mean(hold_times),
            "Avg_IKL": np.mean(ikl_times),
            "IKL_Variance": np.var(ikl_times),
            "Backspace_Count": backspace_count,
            "Mouse_to_Key_Ratio": mouse_ratio, # Match the placeholder from your Tkinter file
            "Pause_Count": sum(1 for t in ikl_times if t > 2000) # Threshold from old file
        }])

        # Probability prediction
        # Use [:, 0][0] to match your old script's extraction logic
        # prob = INTEGRITY_MODEL.predict_proba(features)[:, 0][0]
        # To this:
        prob = INTEGRITY_MODEL.predict_proba(features)[:,0][0] # Probability of Cheating

        return {
            "prob": round(float(prob), 4),
            "is_flagged": bool(
                prob >= 0.6877 or 
                integrity_data.get('paste_count', 0) > 0 or 
                integrity_data.get('switches', 0) > 1
            ),
            "switches": int(integrity_data.get('switches', 0)),
            "backspace_count": int(backspace_count),
            "paste_count": int(integrity_data.get('paste_count', 0))
        }

        '''
        return {
            "prob": round(float(prob), 4),
            "is_flagged": prob >= 0.6877 or integrity_data.get('paste_count', 0) > 0 or integrity_data.get('switches', 0) > 1,
            "switches": integrity_data.get('switches', 0),
            "backspace_count": backspace_count,
            "paste_count": integrity_data.get('paste_count', 0)
        }
        '''

    def process_evaluation(self, user_answer: str, integrity_data: dict, current_num: int, last_q: str):
        """
        Evaluates the candidate's answer with full latency logging.
        """
        eval_overall_start = time.perf_counter()
        
        # 1. RUN INTEGRITY MODEL (Local ML)
        ml_start = time.perf_counter()
        integrity_results = self.run_integrity_model(integrity_data)
        ml_end = time.perf_counter()
        print(f"[TIMER] Local ML Inference: {ml_end - ml_start:.4f}s")

        # 2. CONSTRUCT PROMPT
        # We include all sources: JD, Question, Answer, and Proctoring Facts
        eval_prompt = (
            f"--- ASSESSMENT CONTEXT ---\n"
            f"QUESTION: {last_q}\n"
            f"CANDIDATE ANSWER: {user_answer}\n\n"
            f"--- PROCTORING FACTS ---\n"
            f"Cheating Probability: {integrity_results.get('prob', 0):.4f}\n"
            f"Window Switches: {integrity_results.get('switches', 0)}\n\n"
            f"--- TASK ---\n"
            f"Output ONLY a valid JSON object: {{\"score\": 0-10, \"reasoning\": \"short text\"}}."
        )
        
        # 3. RUN AGENT WITH LATENCY TRACKING
        llm_start = time.perf_counter()
        first_token_time = None
        response_text = ""

        events = self.e_runner.run(
            user_id=self.user_id, 
            session_id=self.session_id, 
            new_message=types.Content(parts=[types.Part(text=eval_prompt)])
        )

        for event in events:
            # Capture Time to First Token (TTFT)
            if first_token_time is None:
                first_token_time = time.perf_counter()
                ttft = first_token_time - llm_start
                print(f"[TIMER] Evaluator TTFT (Thinking/Prefill): {ttft:.4f}s")

            if event.is_final_response() and event.content.parts:
                part = event.content.parts[0]
                if hasattr(part, 'text') and part.text:
                    response_text = part.text

        llm_end = time.perf_counter()

        # 4. SAFETY CHECK FOR SUBTRACTION
        # If the response was so fast that first_token_time wasn't set, use llm_start
        actual_first_token = first_token_time if first_token_time is not None else llm_start
        
        # 5. FINAL LOGGING
        print(f"[TIMER] Evaluator Decoding (Writing JSON): {llm_end - actual_first_token:.4f}s")
        print(f"[TIMER] TOTAL EVALUATION DELAY: {llm_end - eval_overall_start:.4f}s")
        
        # BRUTE-FORCE TERMINAL OUTPUT (Results for you to see)
        print("\n" + "="*50)
        print(f"PROCTORING RESULTS FOR Q{current_num}")
        print(f"Prob: {integrity_results.get('prob', 0):.4f} | Switches: {integrity_results.get('switches', 0)}")
        print("="*50 + "\n")

        return response_text, integrity_results

    # working
    # def process_evaluation(self, user_answer: str, integrity_data: dict, current_num: int, last_q: str):
    #     """
    #     Evaluates the candidate's answer using the ML model and LLM Agent.
    #     Arguments current_num and last_q are now passed directly from the global 
    #     tracker in app_updated.py to ensure accuracy.
    #     """
    #     start_time = time.perf_counter()
        
    #     # 1. RUN INTEGRITY MODEL
    #     # This processes raw keystroke timings through your Gradient Boosting .pkl
    #     integrity_results = self.run_integrity_model(integrity_data)
        
    #     # 2. BRUTE-FORCE TERMINAL OUTPUT
    #     # This provides immediate feedback in the console
    #     print("\n" + "="*50)
    #     print(f"MODEL OUTPUTS FOR QUESTION {current_num}")
    #     print("-" * 50)
    #     print(f"Prob Score : {integrity_results.get('prob'):.4f}")
    #     # print(f"Is Flagged:            {integrity_results.get('is_flagged')}")
    #     print("-" * 50)
    #     print(f"Window Switches:       {integrity_results.get('switches')}")
    #     print(f"Backspace Count:       {integrity_results.get('backspace_count')}")
    #     print(f"Paste Count:           {integrity_results.get('paste_count')}")
    #     print(f"Samples Collected:     {len(integrity_data.get('ikl_times', []))}")
    #     print("="*50 + "\n")

    #     # 3. ENRICHED EVAL_PROMPT
    #     # We explicitly anchor the data to prevent LLM score hallucinations
    #     eval_prompt = (
    #         f"--- ASSESSMENT CONTEXT ---\n"
    #         f"QUESTION: {last_q}\n"
    #         f"CANDIDATE ANSWER: {user_answer}\n\n"
    #         f"--- PROCTORING FACTS (DO NOT MODIFY) ---\n"
    #         f"Keystroke Model Cheating Probability: {integrity_results.get('prob')}\n"
    #         f"Window Switches: {integrity_results.get('switches')}\n\n"
    #         f"--- TASK ---\n"
    #         f"Output ONLY a JSON object: {{\"score\": 0-10, \"reasoning\": \"short text\"}}. "
    #         f"Mention the proctoring facts in your reasoning if the cheating probability is high."
    #     )
        
    #     # 4. RUN AGENT
    #     # The runner still uses the ADK for the LLM conversation
    #     events = self.e_runner.run(
    #         user_id=self.user_id, 
    #         session_id=self.session_id, 
    #         new_message=types.Content(parts=[types.Part(text=eval_prompt)])
    #     )

    #     response_text = ""
    #     for event in events:
    #         if event.is_final_response() and event.content.parts:
    #             part = event.content.parts[0]
    #             if hasattr(part, 'text') and part.text:
    #                 response_text = part.text

    #     # Return the integrity results along with response so app_updated can log them
    #     return response_text, integrity_results
    

    # Added by Souhardya on 12/2 10:32 to update this function

    def export_proctoring_json(self, logs):
        """Saves the global session_logs to a JSON file using the required naming convention."""
        import json
        from datetime import datetime
        import numpy as np

        def make_json_safe(obj):
            if isinstance(obj, dict):
                return {k: make_json_safe(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_json_safe(v) for v in obj]
            elif isinstance(obj, (np.integer,)):
                return int(obj)
            elif isinstance(obj, (np.floating,)):
                return float(obj)
            elif isinstance(obj, (np.bool_,)):
                return bool(obj)
            else:
                return obj

        date_str = datetime.now().strftime('%Y-%m-%d')
        filename = f"keystroke_{self.user_id}_{date_str}.json"
        filepath = self.log_dir / filename

        export_data = {
            "candidate_id": self.user_id,
            "date": date_str,
            "total_questions": len(logs),
            "assessment_data": logs
        }

        try:
            safe_data = make_json_safe(export_data)

            #--------------changing on 12/2 10:50 to force complete disk write immediately, to avoid data loss in case of crashes----------------
            with open(filepath, 'w') as f:
                json.dump(safe_data, f, indent=4)

            '''with open(filepath, 'w') as f:
                json.dump(safe_data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())'''


            print(f"\n[SYSTEM] SUCCESS: Proctoring logs saved as {filename}")

        except Exception as e:
            print(f"[SYSTEM] ERROR: Failed to save logs: {e}")


    '''
    def export_proctoring_json(self, logs):
        """Saves the global session_logs to a JSON file using the required naming convention."""
        # 1. Generate the date string (e.g., 2026-02-09)
        import json
        from datetime import datetime
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        # 2. Construct the filename: keystroke_candidateid_date.json
        filename = f"keystroke_{self.user_id}_{date_str}.json"
        filepath = self.log_dir / filename
        
        export_data = {
            "candidate_id": self.user_id,
            "date": date_str,
            "total_questions": len(logs),
            "assessment_data": logs
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=4)
            print(f"\n[SYSTEM] SUCCESS: Proctoring logs saved as {filename}")
        except Exception as e:
            print(f"[SYSTEM] ERROR: Failed to save logs: {e}")


'''
    #-------------------------------------------------------------------------------