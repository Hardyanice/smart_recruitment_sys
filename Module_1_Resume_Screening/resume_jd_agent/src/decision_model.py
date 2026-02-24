# src/decision_model.py
def make_decision(score, coverage):
    if score >= 65 and coverage >= 0.5:
        return "Selected"
    elif score >= 50:
        return "Borderline"
    else:
        return "Rejected"
