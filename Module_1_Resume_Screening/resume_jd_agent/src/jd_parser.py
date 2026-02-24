import re
import nltk
from nltk.corpus import stopwords
from nltk import pos_tag, word_tokenize

nltk.download("punkt", quiet=True)
nltk.download("averaged_perceptron_tagger", quiet=True)
nltk.download("stopwords", quiet=True)

STOPWORDS = set(stopwords.words("english"))

def extract_jd_requirements(jd_text):
    """
    Extract noun-based requirement phrases from JD
    """
    tokens = word_tokenize(jd_text.lower())
    tagged = pos_tag(tokens)

    requirements = []
    current = []

    for word, tag in tagged:
        if word in STOPWORDS:
            continue
        if tag.startswith("NN") or tag.startswith("JJ"):
            current.append(word)
        else:
            if len(current) >= 2:
                requirements.append(" ".join(current))
            current = []

    if len(current) >= 2:
        requirements.append(" ".join(current))

    # Clean duplicates & noise
    requirements = list(set(r for r in requirements if len(r) > 6))
    return requirements[:15]  # limit noise
