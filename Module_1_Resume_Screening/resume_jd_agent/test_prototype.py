from src.resume_evaluator import evaluate_resume

# -----------------------------
# SAMPLE TEST JD
# -----------------------------
jd_text = """
We are hiring a Machine Learning Engineer with experience in Python,
Scikit-learn, Deep Learning, TensorFlow, Model Deployment,
Neural Networks, and Data Preprocessing.
"""

# -----------------------------
# SAMPLE TEST RESUME
# -----------------------------
resume_text = """
Machine Learning Engineer with strong experience in Python and Scikit-learn.
Worked on Deep Learning models using TensorFlow and implemented
Neural Networks for classification problems. Experienced in
model deployment using Flask APIs.
"""

# -----------------------------
# RUN EVALUATION
# -----------------------------
result = evaluate_resume(resume_text, jd_text, debug=True)

print("\n" + "="*60)
print("FINAL SCORE:", result["score"])
print("RECOMMENDATION:", result["recommendation"])

print("\nBREAKDOWN:")
for k, v in result["breakdown"].items():
    print(f"{k}: {v}")

print("\n" + "="*60)
print("STRONG MATCHES:")
for item in result["matched_requirements"]:
    print(f"\nRequirement: {item['requirement']}")
    print("Matched Concepts:", item.get("matched_concepts", []))
    print("Match %:", item.get("match_percentage"))

print("\n" + "="*60)
print("PARTIAL MATCHES:")
for item in result["partial_matches"]:
    print(f"\nRequirement: {item['requirement']}")
    print("Matched Concepts:", item.get("matched_concepts", []))
    print("Missing Concepts:", item.get("missing_concepts", []))
    print("Match %:", item.get("match_percentage"))

print("\n" + "="*60)
print("MISSING REQUIREMENTS:")
for item in result["missing_requirements"]:
    print(f"\nRequirement: {item['requirement']}")
    print("Missing Concepts:", item.get("missing_concepts", []))

print("\n" + "="*60)
print("FEEDBACK:")
for f in result["feedback"]:
    print("-", f)

print("\n" + "="*60)
