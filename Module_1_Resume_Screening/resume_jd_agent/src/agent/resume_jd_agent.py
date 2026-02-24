from src.agent.resume_evaluator import evaluate_resume

def screen_resume(resume_text, jd_text):
    result = evaluate_resume(resume_text, jd_text)

    decision = "Rejected"
    if result["score"] >= 60:
        decision = "Shortlisted"
    elif result["score"] >= 40:
        decision = "Manual Review"

    return {
        "final_score": result["score"],
        "coverage": result["coverage"],
        "decision": decision,
        "matched_requirements": result["matched_requirements"],
        "missing_requirements": result["missing_requirements"]
    }
