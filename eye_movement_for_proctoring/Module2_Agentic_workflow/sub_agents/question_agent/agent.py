# sub_agents\question_agent\agent.py

import os
from pathlib import Path
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent


# 1. Load Environment Variables from the local .env
# Absolute path ensures the Flask app can find this regardless of launch directory
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

question_agent = Agent(
    # model='gemini-2.5-flash',
    # model = 'gemini-2.5-flash-lite',
    model='gemini-3-flash-preview',
    name='question_agent',
    description='A Senior Technical Interviewer generating JD-based questions.',
    instruction="""
    Role: Senior Recruitment Engineer.
    
    Task: 
    Generate ONE highly concise, technical, open-ended question based ONLY on the provided Job Description (JD).
    Constraints:
    - Output ONLY the question text.
    - NO introductory text (e.g., "Here is your next question").
    - NO conversational filler.
    - Ensure the question is specific and technical.
    """,
    # Explicitly empty tools to prevent 'function_call' latency
    tools=[] 
)