import PyPDF2
import os
from google.adk.tools.tool_context import ToolContext

def load_jd_content(file_path: str = 'jd/sample_jd.pdf') -> str:
    """Reads the JD and returns text for the agent."""
    if not os.path.exists(file_path):
        return "Error: JD file not found at " + file_path
    
    try:
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            return "".join([page.extract_text() for page in reader.pages])
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

    
def increment_question_count(tool_context: ToolContext):
    """Updates the session state to track how many questions have been asked."""
    # Access the live state from the context
    state = tool_context.state
    
    # Increment the count
    current_count = state.get("question_count", 0)
    state["question_count"] = current_count + 1
    
    # Return a confirmation so the model knows the tool succeeded
    return f"Question count updated to {state['question_count']}"