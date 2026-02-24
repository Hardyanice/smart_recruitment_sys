def infer_role(text):
    role_keywords = {
        "Customer Support": ["customer", "support", "ticket", "crm"],
        "Data Science": ["machine learning", "model", "prediction", "statistics"],
        "Software": ["java", "backend", "frontend", "api", "developer"]
    }

    scores = {role: 0 for role in role_keywords}

    for role, keywords in role_keywords.items():
        for kw in keywords:
            if kw in text:
                scores[role] += 1

    return max(scores, key=scores.get)
