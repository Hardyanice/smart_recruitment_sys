from src.similarity import semantic_similarity

def compute_final_score(resume_text, jd_text, coverage_score):
    semantic = semantic_similarity(jd_text, resume_text)

    final_score = (
        0.6 * semantic +
        0.4 * coverage_score
    )

    return round(final_score, 2)
