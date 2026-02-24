"""
Resume Evaluator - FIXED VERSION
Corrected import paths and enhanced debugging
"""

from src.similarity import semantic_similarity
from src.jd_llm_parser import extract_jd_requirements
from src.resume_extractor import extract_resume_terms
import re
from typing import Dict, List, Tuple, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def evaluate_resume(resume_text: str, jd_text: str, debug: bool = False) -> Dict:
    """
    Evaluate resume against job description with comprehensive matching and scoring.
    
    Args:
        resume_text: Full resume text
        jd_text: Full job description text
        debug: Enable detailed debug logging
    
    Returns:
        Dictionary with score, breakdown, matches, and recommendations
    """
    
    try:
        # Input validation
        if not resume_text or not resume_text.strip():
            logger.error("Empty resume text provided")
            return _get_error_response("Empty resume text")
        
        if not jd_text or not jd_text.strip():
            logger.error("Empty JD text provided")
            return _get_error_response("Empty job description")
        
        if debug:
            logger.info(f"Resume length: {len(resume_text)} chars")
            logger.info(f"JD length: {len(jd_text)} chars")
        
        # Extract structured requirements and resume terms
        jd_groups = extract_jd_requirements(jd_text, use_fallback=True, debug=debug)
        resume_terms = extract_resume_terms(resume_text)
        
        if debug:
            logger.info(f"Extracted {len(jd_groups)} JD requirement groups")
            logger.info(f"Extracted {len(resume_terms)} resume terms")
            if resume_terms:
                sample_terms = list(resume_terms)[:10]
                logger.info(f"Sample resume terms: {sample_terms}")
        
        # Handle case where extraction failed
        if not jd_groups:
            logger.warning("No JD requirements extracted - using fallback")
            return _get_fallback_response(resume_text, jd_text)
        
        if not resume_terms:
            logger.warning("No resume terms extracted - low match expected")
        
        # Normalize resume terms for matching
        resume_terms_lower = set(term.lower().strip() for term in resume_terms if term)
        
        # Enhanced matching with multiple strategies
        matched, partial_matched, missing, requirement_scores = _match_requirements(
            jd_groups, 
            resume_terms_lower,
            debug
        )
        
        # Calculate coverage metrics
        total_requirements = len(jd_groups)
        strong_match_count = len(matched)
        partial_match_count = len(partial_matched)
        
        # Weighted coverage score
        coverage_score = sum(requirement_scores) / max(total_requirements, 1) if total_requirements > 0 else 0.0
        
        if debug:
            logger.info(f"Coverage: {coverage_score:.2%} (Strong: {strong_match_count}, Partial: {partial_match_count}, Missing: {len(missing)})")
        
        # Enhanced semantic similarity with error handling
        semantic_score = _calculate_semantic_score(
            jd_text, 
            resume_text, 
            jd_groups, 
            resume_terms_lower,
            debug
        )
        
        if debug:
            logger.info(f"Semantic score: {semantic_score:.2%}")
        
        # Calculate final score with improved weighting
        final_score = calculate_weighted_score(
            semantic_score=semantic_score,
            coverage_score=coverage_score,
            strong_matches=strong_match_count,
            partial_matches=partial_match_count,
            total_requirements=total_requirements
        )
        
        # Generate actionable feedback
        feedback = generate_feedback(
            matched=matched,
            partial_matched=partial_matched,
            missing=missing,
            coverage_score=coverage_score,
            semantic_score=semantic_score,
            final_score=final_score
        )
        
        return {
            "score": round(final_score, 2),
            "breakdown": {
                "semantic_score": round(semantic_score * 100, 2),
                "coverage_score": round(coverage_score * 100, 2),
                "strong_matches": strong_match_count,
                "partial_matches": partial_match_count,
                "missing_count": len(missing),
                "total_requirements": total_requirements
            },
            "matched_requirements": matched,
            "partial_matches": partial_matched,
            "missing_requirements": missing,
            "feedback": feedback,
            "recommendation": get_recommendation(final_score),
            "debug_info": {
                "resume_terms_count": len(resume_terms),
                "jd_groups_count": len(jd_groups)
            } if debug else None
        }
        
    except Exception as e:
        logger.error(f"Evaluation failed: {str(e)}", exc_info=True)
        return _get_error_response(f"Evaluation error: {str(e)}")


def _match_requirements(jd_groups: List[Dict], 
                       resume_terms_lower: set, 
                       debug: bool = False) -> Tuple[List, List, List, List]:
    """
    Match JD requirements against resume terms with multiple matching strategies.
    
    Returns:
        Tuple of (matched, partial_matched, missing, requirement_scores)
    """
    matched = []
    partial_matched = []
    missing = []
    requirement_scores = []
    
    for idx, group in enumerate(jd_groups):
        req = group.get("requirement", "Unknown")
        concepts = [c.lower().strip() for c in group.get("concepts", []) if c]
        
        if not concepts:
            if debug:
                logger.warning(f"Requirement '{req}' has no concepts - skipping")
            continue
        
        # Multiple matching strategies for better coverage
        found_concepts = set()
        
        for concept in concepts:
            if _is_concept_matched(concept, resume_terms_lower):
                found_concepts.add(concept)
        
        found_concepts = list(found_concepts)
        match_ratio = len(found_concepts) / len(concepts)
        
        if debug and idx < 5:  # Log first 5 for debugging
            logger.info(f"Requirement: '{req}' - {len(found_concepts)}/{len(concepts)} concepts matched ({match_ratio:.0%})")
        
        # Categorize based on match strength with adjusted thresholds
        if match_ratio >= 0.6:  # Strong match (60%+ concepts found)
            matched.append({
                "requirement": req,
                "matched_concepts": found_concepts[:10],  # Top 10
                "match_strength": "strong",
                "match_percentage": round(match_ratio * 100, 1)
            })
            requirement_scores.append(1.0)
            
        elif match_ratio >= 0.25:  # Partial match (25-60% concepts found)
            partial_matched.append({
                "requirement": req,
                "matched_concepts": found_concepts,
                "missing_concepts": [c for c in concepts if c not in found_concepts][:5],
                "match_strength": "partial",
                "match_percentage": round(match_ratio * 100, 1)
            })
            requirement_scores.append(0.5)
            
        else:  # Weak/no match (<25% concepts found)
            missing.append({
                "requirement": req,
                "missing_concepts": concepts[:8],  # Show more for context
                "priority": group.get("experience_level", "unknown"),
                "category": group.get("category", "general")
            })
            requirement_scores.append(0.0)
    
    return matched, partial_matched, missing, requirement_scores


def _is_concept_matched(concept: str, resume_terms: set) -> bool:
    """
    Check if a concept is matched in resume terms.
    Uses multiple matching strategies: exact, substring, fuzzy.
    """
    concept = concept.lower().strip()
    
    # Strategy 1: Exact match
    if concept in resume_terms:
        return True
    
    # Strategy 2: Concept is substring of any resume term
    for term in resume_terms:
        if concept in term or term in concept:
            # Avoid false positives on very short terms
            if len(concept) >= 3 or len(term) >= 3:
                return True
    
    # Strategy 3: Multi-word concepts - check if all words present
    if ' ' in concept:
        words = concept.split()
        if all(word in resume_terms or any(word in t for t in resume_terms) for word in words):
            return True
    
    # Strategy 4: Acronym expansion (e.g., "ML" matches "machine learning")
    acronym_map = {
        'ml': ['machine', 'learning'],
        'ai': ['artificial', 'intelligence'],
        'nlp': ['natural', 'language', 'processing'],
        'cv': ['computer', 'vision'],
        'aws': ['amazon', 'web', 'services'],
        'gcp': ['google', 'cloud', 'platform'],
        'sql': ['structured', 'query', 'language'],
        'api': ['application', 'programming', 'interface'],
    }
    
    if concept in acronym_map:
        expansion_words = acronym_map[concept]
        if all(word in resume_terms or any(word in t for t in resume_terms) for word in expansion_words):
            return True
    
    return False


def _calculate_semantic_score(jd_text: str, 
                              resume_text: str, 
                              jd_groups: List[Dict],
                              resume_terms: set,
                              debug: bool = False) -> float:
    """
    Calculate semantic similarity between JD and resume.
    Falls back to keyword matching if embedding fails.
    """
    try:
        # Truncate for efficiency
        jd_sample = jd_text[:2000]
        resume_sample = resume_text[:3000]
        
        # Try semantic similarity with embeddings
        similarity = semantic_similarity(jd_sample, resume_sample)
        
        if debug:
            logger.info(f"Embedding-based similarity: {similarity:.3f}")
        
        return similarity
        
    except Exception as e:
        logger.warning(f"Semantic similarity failed, using keyword fallback: {e}")
        
        # Fallback: Keyword-based similarity
        jd_words = set(jd_text.lower().split())
        overlap = len(resume_terms & jd_words)
        total_jd_words = len(jd_words)
        
        fallback_score = min(overlap / max(total_jd_words, 1), 1.0) if total_jd_words > 0 else 0.0
        
        if debug:
            logger.info(f"Keyword-based similarity: {fallback_score:.3f} ({overlap}/{total_jd_words} words)")
        
        return fallback_score


def calculate_weighted_score(semantic_score: float,
                            coverage_score: float,
                            strong_matches: int,
                            partial_matches: int,
                            total_requirements: int) -> float:
    """
    Calculate final weighted score with balanced components.
    
    Components:
    - Semantic similarity: 40%
    - Coverage score: 40%  
    - Match bonuses: +12%
    - Partial bonuses: +5%
    - Missing penalties: -12%
    """
    
    # Base score (80% weight)
    base_score = (semantic_score * 0.40) + (coverage_score * 0.40)
    
    # Bonus for strong matches (up to +12%)
    strong_bonus = 0.0
    if total_requirements > 0 and strong_matches > 0:
        strong_match_ratio = min(strong_matches / total_requirements, 0.75)  # Cap at 75%
        strong_bonus = min(0.12, strong_match_ratio * 0.16)
    
    # Small bonus for partial matches (up to +5%)
    partial_bonus = 0.0
    if total_requirements > 0 and partial_matches > 0:
        partial_ratio = min(partial_matches / total_requirements, 0.5)  # Cap at 50%
        partial_bonus = min(0.05, partial_ratio * 0.10)
    
    # Penalty for missing requirements (up to -12%)
    missing_penalty = 0.0
    missing_count = total_requirements - strong_matches - partial_matches
    if total_requirements > 0:
        missing_ratio = missing_count / total_requirements
        
        # Progressive penalty
        if missing_ratio > 0.70:
            missing_penalty = 0.12
        elif missing_ratio > 0.50:
            missing_penalty = 0.09
        elif missing_ratio > 0.30:
            missing_penalty = 0.06
        else:
            missing_penalty = missing_ratio * 0.15
    
    # Minimum score floor for reasonable semantic/coverage
    if semantic_score >= 0.40 or coverage_score >= 0.40:
        min_floor = 0.25  # At least 25/100 if showing some relevance
    else:
        min_floor = 0.0
    
    # Calculate final score
    final_score = base_score + strong_bonus + partial_bonus - missing_penalty
    final_score = max(min_floor, final_score)
    
    # Convert to 0-100 scale
    return max(0.0, min(100.0, final_score * 100))


def generate_feedback(matched: List[Dict], 
                     partial_matched: List[Dict], 
                     missing: List[Dict], 
                     coverage_score: float, 
                     semantic_score: float,
                     final_score: float) -> List[str]:
    """
    Generate actionable, prioritized feedback.
    """
    feedback = []
    
    # Overall assessment
    if final_score >= 75:
        feedback.append("✓ Excellent match - Strong alignment with job requirements")
    elif final_score >= 60:
        feedback.append("✓ Good match - Most key requirements met")
    elif final_score >= 45:
        feedback.append("○ Moderate match - Some relevant skills present")
    elif final_score >= 30:
        feedback.append("⚠ Limited match - Significant skill gaps")
    else:
        feedback.append("⚠ Poor match - Major requirements missing")
    
    # Coverage-specific feedback
    if coverage_score >= 0.75:
        feedback.append(f"✓ Strong requirement coverage ({len(matched)} strong matches)")
    elif coverage_score >= 0.50:
        feedback.append(f"○ Moderate coverage ({len(matched)} strong, {len(partial_matched)} partial)")
    elif coverage_score >= 0.25:
        feedback.append(f"⚠ Low coverage - only {len(matched)} requirements fully matched")
    else:
        feedback.append(f"⚠ Very low coverage - {len(missing)} critical requirements missing")
    
    # Semantic-specific feedback
    if semantic_score >= 0.65:
        feedback.append("✓ Strong semantic alignment - relevant experience evident")
    elif semantic_score >= 0.45:
        feedback.append("○ Moderate alignment - some relevant context")
    else:
        feedback.append("⚠ Weak semantic match - emphasize relevant experience more")
    
    # Actionable recommendations
    if len(partial_matched) >= 3:
        feedback.append(f"→ {len(partial_matched)} partial matches - strengthen and highlight these")
    
    if len(missing) > 0:
        high_priority = [m for m in missing if m.get("priority") in ["senior", "expert"]]
        if high_priority:
            feedback.append(f"⚠ {len(high_priority)} high-priority requirements missing")
        elif len(missing) > 5:
            feedback.append(f"→ {len(missing)} requirements not matched - consider skill development")
    
    # Positive reinforcement
    if len(matched) >= 5:
        feedback.append(f"✓ Strong showing in {len(matched)} key areas")
    
    return feedback


def get_recommendation(score: float) -> str:
    """
    Provide clear application recommendation with reasoning.
    """
    if score >= 80:
        return "STRONG MATCH - Highly recommended to apply. Your profile aligns very well."
    elif score >= 65:
        return "GOOD MATCH - Recommended to apply. Tailor resume to emphasize matching skills."
    elif score >= 50:
        return "MODERATE MATCH - Consider applying. Highlight transferable skills and relevant experience."
    elif score >= 35:
        return "WEAK MATCH - Gaps present. Apply only if willing to learn or can demonstrate transferable experience."
    else:
        return "POOR MATCH - Not recommended. Significant skill development needed for this role."


def _get_error_response(error_msg: str) -> Dict:
    """
    Return standardized error response.
    """
    return {
        "score": 0.0,
        "error": error_msg,
        "breakdown": {
            "semantic_score": 0.0,
            "coverage_score": 0.0,
            "strong_matches": 0,
            "partial_matches": 0,
            "missing_count": 0,
            "total_requirements": 0
        },
        "matched_requirements": [],
        "partial_matches": [],
        "missing_requirements": [],
        "feedback": [f"⚠ Error: {error_msg}"],
        "recommendation": "Unable to evaluate - please check inputs"
    }


def _get_fallback_response(resume_text: str, jd_text: str) -> Dict:
    """
    Fallback evaluation using only semantic similarity.
    """
    try:
        semantic_score = semantic_similarity(jd_text[:2000], resume_text[:3000])
        final_score = semantic_score * 100 if semantic_score else 0.0
        
        return {
            "score": round(final_score, 2),
            "breakdown": {
                "semantic_score": round(semantic_score * 100, 2) if semantic_score else 0.0,
                "coverage_score": 0.0,
                "strong_matches": 0,
                "partial_matches": 0,
                "missing_count": 0,
                "total_requirements": 0
            },
            "matched_requirements": [],
            "partial_matches": [],
            "missing_requirements": [],
            "feedback": [
                "○ Using simplified evaluation (requirement extraction failed)",
                f"○ Semantic similarity: {semantic_score:.0%}" if semantic_score else "⚠ Low semantic match"
            ],
            "recommendation": get_recommendation(final_score)
        }
    except Exception as e:
        logger.error(f"Fallback evaluation failed: {e}")
        return _get_error_response("Both primary and fallback evaluation failed")