import PyPDF2
import os
from google.adk.tools.tool_context import ToolContext


def read_job_description(file_path='jd/sample_jd.pdf'):
    """
    Reads the JD text to provide context for technical grading.
    """
    if not os.path.exists(file_path):
        return "Error: Job Description file not found."
        
    try:
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text
    except Exception as e:
        return f"Error reading PDF: {str(e)}"
    

def record_and_grade(
    tool_context: ToolContext, 
    question: str, 
    answer: str, 
    score: str, 
    prob: float, 
    backspaces: int, 
    switches: int, 
    pastes: int
):
    """Saves the full technical answer and integrity metrics to the session state."""
    state = tool_context.state
    
    # Structure the detailed log entry
    turn_log = {
        "question_number": state.get("question_count", 0),
        "question": question,
        "answer": answer,
        "score": score,
        "integrity_metrics": {
            "bot_probability": prob,
            "backspace_count": backspaces,
            "window_switches": switches,
            "paste_count": pastes
        }
    }
    
    # Save to 'question_wise_logs' for your final JSON export
    logs = state.get("question_wise_logs", [])
    logs.append(turn_log)
    state["question_wise_logs"] = logs
    
    return f"Turn data for Question {state.get('question_count')} successfully registered in session state."


def record_assessment_data(
    tool_context: ToolContext, 
    answer: str, 
    score: str, 
    reasoning: str, 
    prob: float, 
    backspaces: int, 
    switches: int, 
    pastes: int
):
    """Saves everything to the session state."""
    state = tool_context.state
    
    # Use the question text from state or a placeholder
    q_text = state.get("last_question_text", "Technical Question")
    
    turn_log = {
        "question_number": state.get("question_count", 0),
        "question_text": q_text,
        "candidate_answer": answer, # Save the actual answer passed from the agent turn
        "score": score,
        "reasoning": reasoning,
        "integrity_metrics": {
            "bot_probability": prob,
            "backspace_count": backspaces,
            "window_switches": switches,
            "paste_count": pastes
        }
    }
    
    # Update the list
    logs = state.get("question_wise_logs", [])
    logs.append(turn_log)
    state["question_wise_logs"] = logs
    
    return f"Turn {state.get('question_count')} logged successfully."