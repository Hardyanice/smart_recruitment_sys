# sub_agents\evaluator_agent\agent.py

import os
from pathlib import Path
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

# groq_model = LiteLlm(model="groq/llama-3.3-70b-versatile")

evaluator_agent = Agent(
    # model=groq_model,
    # model = 'gemini-2.5-flash',
    # model = 'gemini-2.5-flash-lite',
    model='gemini-3-flash-preview',
    name='evaluator_agent',
    instruction="""
    Role: Senior Technical Interviewer.
    
    Task: Evaluate the candidate's answer based on the provided Technical Question and Proctoring Facts.
    
    Constraints:
    1. Assess the technical accuracy of the answer (Score: 0-10).
    2. Consider the 'Keystroke Model Cheating Probability'. If it is high (e.g., > 0.7), mention this as a concern in your reasoning.
    3. Output ONLY a valid JSON object.
    4. Do NOT include any introductory or concluding text.
    
    Output Format:
    {
      "score": <integer>,
      "reasoning": "<concise explanation referencing both technical content and integrity data>"
    }
    """,
    tools=[]
)

