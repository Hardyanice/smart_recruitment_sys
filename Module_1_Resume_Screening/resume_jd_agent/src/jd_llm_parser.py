import json
import re
from typing import List, Dict, Optional, Set
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# COMPREHENSIVE STOPWORD LIST - Technical context aware
STOPWORDS = {
    # Common English stopwords
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'has', 'have',
    'in', 'is', 'it', 'its', 'of', 'on', 'or', 'that', 'the', 'to', 'was', 'will',
    'with', 'we', 'our', 'you', 'your', 'this', 'these', 'those', 'them', 'they',
    'their', 'there', 'here', 'where', 'when', 'what', 'who', 'which', 'how', 'why',
    
    # Job description fluff
    'ability', 'able', 'across', 'advantage', 'all', 'also', 'any', 'around',
    'background', 'based', 'best', 'between', 'both', 'can', 'could', 'create',
    'developing', 'development', 'different', 'do', 'each', 'environment',
    'every', 'excellent', 'experience', 'fast', 'first', 'good', 'great', 'help',
    'high', 'highly', 'including', 'industry', 'into', 'join', 'knowledge',
    'large', 'lead', 'leading', 'learn', 'level', 'like', 'looking', 'make',
    'making', 'manage', 'management', 'many', 'may', 'more', 'most', 'much',
    'must', 'need', 'new', 'not', 'now', 'off', 'one', 'only', 'opportunity',
    'other', 'others', 'out', 'over', 'own', 'part', 'people', 'per', 'plus',
    'position', 'preferred', 'process', 'provide', 'providing', 'quality',
    'related', 'required', 'requirements', 'role', 'same', 'scalable', 'scale',
    'see', 'senior', 'several', 'should', 'skill', 'skills', 'some', 'strong',
    'such', 'support', 'system', 'systems', 'take', 'team', 'teams', 'than',
    'through', 'time', 'top', 'under', 'understanding', 'up', 'use', 'used',
    'using', 'very', 'want', 'way', 'well', 'while', 'within', 'work', 'working',
    'would', 'year', 'years',
    
    # Soft skills to ignore
    'communication', 'teamwork', 'leadership', 'collaborative', 'motivated',
    'passionate', 'dedicated', 'enthusiastic', 'proactive', 'detail-oriented',
    'self-motivated', 'organized', 'analytical', 'problem-solving', 'creative',
    
    # Location/company fluff
    'location', 'office', 'remote', 'hybrid', 'salary', 'benefits', 'culture',
    'company', 'organization', 'business', 'enterprise', 'startup',
    
    # Meaningless modifiers
    'etc', 'i.e', 'e.g', 'ie', 'eg', 'various', 'multiple', 'diverse', 'range',
}

# Minimum concept quality thresholds
MIN_CONCEPT_LENGTH = 2  # Changed from 2 to allow 'ML', 'AI', 'JS'
MIN_WORD_TOKENS = 1  # But single word must pass strict validation
MIN_CONCEPTS_PER_REQUIREMENT = 3
MAX_CONCEPTS_PER_REQUIREMENT = 20


def extract_jd_requirements(jd_text: str, use_fallback: bool = True, debug: bool = False) -> List[Dict]:
    """
    Extract job requirements as rich concept groups with semantic expansion.
    
    Args:
        jd_text: Job description text
        use_fallback: Use regex fallback if LLM fails
        debug: Enable detailed logging
    
    Returns:
        List of requirement dictionaries with concepts and metadata
    """
    
    # Input validation
    if not jd_text or not jd_text.strip():
        logger.error("Empty JD text provided")
        return []
    
    if len(jd_text) < 50:
        logger.warning("Very short JD text - may have limited extraction")
    
    if debug:
        logger.info(f"JD text length: {len(jd_text)} characters")
    
    # Try LLM-based extraction first
    try:
        requirements = _extract_with_llm(jd_text, debug)
        
        if requirements and len(requirements) > 0:
            if debug:
                logger.info(f"LLM extraction successful: {len(requirements)} requirements")
            return requirements
        else:
            logger.warning("LLM extraction returned empty results")
            
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
    
    # Fallback to regex-based extraction
    if use_fallback:
        logger.info("Using fallback regex extraction")
        return _extract_with_regex(jd_text, debug)
    
    return []


def _extract_with_llm(jd_text: str, debug: bool = False) -> List[Dict]:
    """
    Extract requirements using LLM with improved prompt and error handling.
    """
    from src.llm_client import call_llm
    
    # Truncate very long JDs
    max_length = 4000
    if len(jd_text) > max_length:
        logger.warning(f"JD text truncated from {len(jd_text)} to {max_length} chars")
        jd_text = jd_text[:max_length] + "..."
    
    prompt = f"""You are an expert technical recruiter specializing in semantic skill extraction.

TASK: Extract job requirements as RICH CONCEPT GROUPS for semantic matching.

CRITICAL EXTRACTION RULES:
1. **Multi-level concepts**: Include core skill + variations + related technologies
2. **Semantic synonyms**: Add alternative terms and abbreviations
   - Example: "ML" = "Machine Learning" = "machine learning"
3. **Context preservation**: Include domain context when mentioned
4. **Tool ecosystem**: Group tools with their alternatives
5. **Experience indicators**: Extract years, proficiency levels if mentioned
6. **Expand acronyms**: ALWAYS include both full form AND abbreviation

CONCEPT EXPANSION EXAMPLES (FOLLOW THESE PATTERNS):
- "Python" → ["Python", "Python programming", "Python development", "Python 3", "Python3", "py", "scripting", "Python coding"]
- "AWS" → ["AWS", "Amazon Web Services", "Amazon AWS", "cloud", "EC2", "S3", "Lambda", "cloud computing", "AWS cloud"]
- "Machine Learning" → ["Machine Learning", "ML", "machine learning", "supervised learning", "unsupervised learning", "regression", "classification", "neural networks", "model training", "predictive modeling", "AI", "artificial intelligence"]
- "Django" → ["Django", "Django framework", "Django REST", "DRF", "Django REST framework", "Python Django", "web framework"]
- "SQL" → ["SQL", "Structured Query Language", "database queries", "MySQL", "PostgreSQL", "SQLite", "database", "RDBMS"]
- "REST API" → ["REST", "REST API", "RESTful", "API", "web services", "HTTP API", "JSON API", "API development"]

STRICT FILTERING REQUIREMENTS:
- NO single-word generic terms like "We", "The", "Team", "Work", "Strong"
- NO soft skills (communication, teamwork, leadership)
- NO stopwords or filler words
- ONLY technical skills, tools, frameworks, languages, platforms, methodologies
- Each concept MUST be meaningful and searchable

WHAT TO IGNORE:
- Soft skills (communication, teamwork, leadership)
- Company benefits, perks, culture
- Generic phrases ("fast-paced environment", "dynamic team")
- Location, salary, company description
- Meaningless words (we, the, our, your, strong, excellent)

OUTPUT FORMAT (STRICT JSON ARRAY):
[
  {{
    "requirement": "Primary skill or concept (e.g., 'Python', 'Machine Learning')",
    "concepts": ["synonym1", "variation1", "related_tool1", "abbreviation1", "related_method1"],
    "category": "programming_language|framework|cloud|database|methodology|domain|tool",
    "experience_level": "junior|mid|senior|expert|null",
    "context": "Brief domain or application context if mentioned, otherwise null"
  }}
]

QUALITY REQUIREMENTS:
- Each requirement MUST have 5-15 related concepts minimum
- Include BOTH full forms AND abbreviations
- Include common variations and synonyms
- Return ONLY valid JSON array, NO markdown, NO explanations, NO preamble
- If uncertain about a requirement, still include it with best-effort concepts
- NEVER include stopwords, generic terms, or soft skills in concepts

Job Description:
{jd_text}

Return ONLY the JSON array now:"""

    try:
        if debug:
            logger.info("Calling LLM for requirement extraction...")
        
        response = call_llm(prompt)
        
        if not response:
            logger.error("LLM returned empty response")
            return []
        
        if debug:
            logger.info(f"LLM response length: {len(response)} characters")
            logger.info(f"Response preview: {response[:200]}...")
        
        # Clean response
        cleaned_response = _clean_llm_response(response)
        
        if debug:
            logger.info(f"Cleaned response preview: {cleaned_response[:200]}...")
        
        # Parse JSON with strict validation
        requirements = _parse_and_validate_json(cleaned_response, debug)
        
        if not requirements:
            logger.error("JSON parsing/validation failed")
            return []
        
        # Post-process and validate
        enhanced_requirements = _post_process_requirements(requirements, debug)
        
        return enhanced_requirements
        
    except Exception as e:
        logger.error(f"LLM extraction error: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        return []


def _parse_and_validate_json(json_str: str, debug: bool = False) -> Optional[List[Dict]]:
    """
    Parse JSON with strict validation and error handling.
    """
    try:
        data = json.loads(json_str)
        
        # Must be a list
        if not isinstance(data, list):
            logger.error(f"Expected list, got {type(data)}")
            return None
        
        # Validate each item has required structure
        validated = []
        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                logger.warning(f"Item {idx} is not a dict, skipping")
                continue
            
            # Must have requirement and concepts
            if 'requirement' not in item or 'concepts' not in item:
                logger.warning(f"Item {idx} missing required fields, skipping")
                continue
            
            # Concepts must be a list
            if not isinstance(item['concepts'], list):
                logger.warning(f"Item {idx} concepts is not a list, skipping")
                continue
            
            validated.append(item)
        
        if debug:
            logger.info(f"JSON validation: {len(data)} items → {len(validated)} valid")
        
        return validated if validated else None
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing failed: {e}")
        if debug:
            logger.error(f"Failed to parse: {json_str[:500]}")
        return None


def _clean_llm_response(response: str) -> str:
    """
    Clean LLM response to extract valid JSON.
    """
    response = response.strip()
    
    # Remove markdown code blocks
    if response.startswith("```json"):
        response = response[7:]
    elif response.startswith("```"):
        response = response[3:]
    
    if response.endswith("```"):
        response = response[:-3]
    
    response = response.strip()
    
    # Try to find JSON array boundaries if response has extra text
    if not response.startswith('['):
        # Look for first [ character
        start_idx = response.find('[')
        if start_idx != -1:
            response = response[start_idx:]
    
    if not response.endswith(']'):
        # Look for last ] character
        end_idx = response.rfind(']')
        if end_idx != -1:
            response = response[:end_idx + 1]
    
    return response


def _is_valid_concept(concept: str) -> bool:
    """
    Validate if a concept is meaningful and should be kept.
    
    Filters out:
    - Stopwords
    - Single generic words
    - Too short strings
    - Non-technical terms
    """
    if not isinstance(concept, str):
        return False
    
    concept = concept.strip()
    
    # Minimum length check (allow 2-char for ML, AI, JS, Go, R, etc.)
    if len(concept) < MIN_CONCEPT_LENGTH:
        return False
    
    # Check against stopwords (case-insensitive)
    if concept.lower() in STOPWORDS:
        return False
    
    # Single word must be technical or have special characters
    words = concept.split()
    if len(words) == 1:
        # Allow common technical acronyms/terms even if short
        technical_patterns = [
            r'^[A-Z]{2,}$',  # Acronyms: AWS, SQL, ML, AI
            r'.*[.#+-].*',   # Contains special chars: C#, C++, Node.js
            r'^[A-Z][a-z]*$',  # Title case single words: Python, Java, React
        ]
        
        # Check if matches any technical pattern
        is_technical = any(re.match(pattern, concept) for pattern in technical_patterns)
        
        if not is_technical:
            # Additional check: is it in our known tech terms?
            known_tech = {
                'python', 'java', 'javascript', 'typescript', 'ruby', 'go', 'rust',
                'php', 'swift', 'kotlin', 'scala', 'r', 'matlab', 'julia',
                'react', 'angular', 'vue', 'django', 'flask', 'spring', 'express',
                'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'k8s', 'jenkins',
                'sql', 'nosql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
                'git', 'svn', 'jira', 'confluence', 'slack',
                'ml', 'ai', 'nlp', 'cv', 'dl', 'rl', 'gan',
                'api', 'rest', 'graphql', 'grpc', 'soap',
                'html', 'css', 'sass', 'less', 'webpack', 'babel',
                'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas', 'numpy',
                'linux', 'unix', 'windows', 'macos', 'ios', 'android',
                'agile', 'scrum', 'kanban', 'devops', 'cicd', 'tdd', 'bdd',
            }
            
            if concept.lower() not in known_tech:
                return False
    
    # Must contain at least one letter
    if not re.search(r'[a-zA-Z]', concept):
        return False
    
    # Reject pure numbers
    if concept.isdigit():
        return False
    
    # Reject common garbage patterns
    garbage_patterns = [
        r'^[0-9]+$',  # Pure numbers
        r'^[^a-zA-Z0-9]+$',  # Only special chars
        r'^(we|our|you|your|the|this|that)$',  # Case-insensitive pronouns
    ]
    
    for pattern in garbage_patterns:
        if re.match(pattern, concept, re.IGNORECASE):
            return False
    
    return True


def _clean_and_deduplicate_concepts(concepts: List[str]) -> List[str]:
    """
    Clean, filter, and deduplicate concepts while preserving order.
    
    Returns:
        Cleaned list of unique, valid concepts
    """
    seen = set()
    seen_lower = set()
    cleaned = []
    
    for concept in concepts:
        if not isinstance(concept, str):
            continue
        
        concept = concept.strip()
        
        # Skip if invalid
        if not _is_valid_concept(concept):
            continue
        
        # Check for exact duplicates
        if concept in seen:
            continue
        
        # Check for case-insensitive duplicates
        concept_lower = concept.lower()
        if concept_lower in seen_lower:
            continue
        
        seen.add(concept)
        seen_lower.add(concept_lower)
        cleaned.append(concept)
    
    return cleaned


def _post_process_requirements(requirements: List[Dict], debug: bool = False) -> List[Dict]:
    """
    Post-process and enhance extracted requirements with aggressive filtering.
    """
    enhanced = []
    
    for idx, req in enumerate(requirements):
        try:
            # Validate required fields
            if not isinstance(req, dict):
                logger.warning(f"Requirement {idx} is not a dict: {type(req)}")
                continue
            
            requirement_text = req.get("requirement", "").strip()
            concepts = req.get("concepts", [])
            
            if not requirement_text:
                logger.warning(f"Requirement {idx} has no requirement text")
                continue
            
            # Validate requirement itself
            if not _is_valid_concept(requirement_text):
                if debug:
                    logger.info(f"Requirement '{requirement_text}' failed validation, skipping")
                continue
            
            # Ensure concepts is a list
            if not isinstance(concepts, list):
                concepts = []
            
            # AGGRESSIVE CLEANING AND DEDUPLICATION
            cleaned_concepts = _clean_and_deduplicate_concepts(concepts)
            
            # Ensure requirement is in concepts (if it's valid)
            if requirement_text not in cleaned_concepts:
                cleaned_concepts.insert(0, requirement_text)
            
            # Try to enrich if too few concepts
            if len(cleaned_concepts) < MIN_CONCEPTS_PER_REQUIREMENT:
                if debug:
                    logger.info(f"Enriching requirement '{requirement_text}' with only {len(cleaned_concepts)} concepts")
                
                enriched = _enrich_concepts(requirement_text, cleaned_concepts)
                # Re-clean after enrichment
                cleaned_concepts = _clean_and_deduplicate_concepts(enriched)
            
            # Final check: must have minimum concepts
            if len(cleaned_concepts) < MIN_CONCEPTS_PER_REQUIREMENT:
                if debug:
                    logger.info(f"Skipping requirement '{requirement_text}': only {len(cleaned_concepts)} valid concepts")
                continue
            
            # Limit to max concepts to avoid bloat
            if len(cleaned_concepts) > MAX_CONCEPTS_PER_REQUIREMENT:
                cleaned_concepts = cleaned_concepts[:MAX_CONCEPTS_PER_REQUIREMENT]
            
            # Build enhanced requirement
            enhanced_req = {
                "requirement": requirement_text,
                "concepts": cleaned_concepts,
                "category": req.get("category", "general"),
                "experience_level": req.get("experience_level"),
                "context": req.get("context")
            }
            
            enhanced.append(enhanced_req)
            
        except Exception as e:
            logger.error(f"Error processing requirement {idx}: {e}")
            continue
    
    if debug:
        logger.info(f"Post-processing: {len(requirements)} → {len(enhanced)} requirements")
    
    return enhanced


def _enrich_concepts(requirement: str, existing_concepts: List[str]) -> List[str]:
    """
    Enrich concepts with basic variations if LLM provided too few.
    Only adds valid, technical variations.
    """
    enriched = existing_concepts.copy()
    
    # Add the requirement itself
    if requirement not in enriched:
        enriched.append(requirement)
    
    # Common technical variations (validated)
    variations = {
        'python': ['Python', 'Python3', 'py'],
        'java': ['Java', 'JDK', 'JVM'],
        'javascript': ['JavaScript', 'JS', 'ECMAScript'],
        'typescript': ['TypeScript', 'TS'],
        'aws': ['AWS', 'Amazon Web Services'],
        'azure': ['Azure', 'Microsoft Azure'],
        'gcp': ['GCP', 'Google Cloud Platform', 'Google Cloud'],
        'sql': ['SQL', 'RDBMS'],
        'nosql': ['NoSQL', 'non-relational'],
        'machine learning': ['ML', 'machine-learning'],
        'deep learning': ['DL', 'deep-learning'],
        'artificial intelligence': ['AI'],
        'docker': ['Docker', 'containerization'],
        'kubernetes': ['Kubernetes', 'K8s', 'k8s'],
        'react': ['React', 'ReactJS', 'React.js'],
        'angular': ['Angular', 'AngularJS'],
        'vue': ['Vue', 'Vue.js', 'VueJS'],
        'django': ['Django'],
        'flask': ['Flask'],
        'node': ['Node.js', 'NodeJS'],
        'rest': ['REST', 'RESTful'],
        'graphql': ['GraphQL'],
        'mongodb': ['MongoDB', 'Mongo'],
        'postgresql': ['PostgreSQL', 'Postgres'],
        'mysql': ['MySQL'],
        'redis': ['Redis'],
        'elasticsearch': ['Elasticsearch', 'Elastic'],
        'jenkins': ['Jenkins'],
        'git': ['Git', 'version control'],
        'ci/cd': ['CICD', 'continuous integration'],
        'tensorflow': ['TensorFlow', 'TF'],
        'pytorch': ['PyTorch'],
        'scikit-learn': ['sklearn', 'scikit'],
    }
    
    req_lower = requirement.lower()
    for key, values in variations.items():
        if key in req_lower or req_lower in key:
            for val in values:
                if val not in enriched and _is_valid_concept(val):
                    enriched.append(val)
    
    return enriched


def _extract_with_regex(jd_text: str, debug: bool = False) -> List[Dict]:
    """
    Fallback regex-based extraction when LLM fails.
    Extracts common technical terms and skills with strict filtering.
    """
    
    if debug:
        logger.info("Using regex-based extraction")
    
    requirements = []
    
    # Pattern for programming languages and frameworks (case-sensitive)
    tech_patterns = [
        r'\bPython\b', r'\bJava\b', r'\bJavaScript\b', r'\bTypeScript\b',
        r'\bC\+\+\b', r'\bC#\b', r'\bRuby\b', r'\bGo\b', r'\bRust\b', r'\bPHP\b',
        r'\bReact\b', r'\bAngular\b', r'\bVue\b', r'\bDjango\b', r'\bFlask\b', 
        r'\bSpring\b', r'\bNode\.js\b', r'\bExpress\b',
        r'\bAWS\b', r'\bAzure\b', r'\bGCP\b', r'\bDocker\b', r'\bKubernetes\b', r'\bK8s\b',
        r'\bSQL\b', r'\bNoSQL\b', r'\bMySQL\b', r'\bPostgreSQL\b', r'\bMongoDB\b', r'\bRedis\b',
        r'\bMachine\s+Learning\b', r'\bDeep\s+Learning\b', r'\b(ML|AI|NLP|CV)\b',
        r'\bREST\s+API\b', r'\bGraphQL\b', r'\bAPI\b', r'\bGit\b', r'\bCI/CD\b',
        r'\bTensorFlow\b', r'\bPyTorch\b', r'\bKeras\b', r'\bscikit-learn\b',
        r'\bLinux\b', r'\bUnix\b', r'\bJenkins\b', r'\bGitHub\b', r'\bGitLab\b',
    ]
    
    tech_terms = set()
    for pattern in tech_patterns:
        matches = re.findall(pattern, jd_text)
        tech_terms.update(matches)
    
    # Acronyms (but filter carefully)
    acronyms = re.findall(r'\b[A-Z]{2,}\b', jd_text)
    
    # Only keep technical acronyms
    technical_acronyms = {
        'AWS', 'GCP', 'SQL', 'API', 'REST', 'HTTP', 'HTTPS', 'JSON', 'XML', 'HTML', 'CSS',
        'ML', 'AI', 'NLP', 'CV', 'DL', 'RL', 'CI', 'CD', 'IDE', 'SDK', 'JVM', 'JDK',
        'OOP', 'MVC', 'MVVM', 'TDD', 'BDD', 'CRUD', 'ACID', 'JWT', 'OAuth', 'SOAP',
    }
    
    filtered_acronyms = {acr for acr in acronyms if acr in technical_acronyms}
    tech_terms.update(filtered_acronyms)
    
    # Categorization
    tech_categories = {
        'programming_language': ['Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Ruby', 'Go', 'Rust', 'PHP'],
        'framework': ['React', 'Angular', 'Vue', 'Django', 'Flask', 'Spring', 'Express'],
        'cloud': ['AWS', 'Azure', 'GCP'],
        'database': ['SQL', 'NoSQL', 'MySQL', 'PostgreSQL', 'MongoDB', 'Redis'],
        'devops': ['Docker', 'Kubernetes', 'K8s', 'Jenkins', 'CI/CD', 'Git', 'GitHub', 'GitLab'],
        'domain': ['Machine Learning', 'Deep Learning', 'ML', 'AI', 'NLP', 'CV', 'TensorFlow', 'PyTorch'],
    }
    
    # Build requirements from extracted terms
    for term in tech_terms:
        if not _is_valid_concept(term):
            continue
        
        # Determine category
        category = 'tool'
        for cat, keywords in tech_categories.items():
            if term in keywords:
                category = cat
                break
        
        # Generate enriched concepts
        concepts = _enrich_concepts(term, [term])
        
        # Clean and deduplicate
        concepts = _clean_and_deduplicate_concepts(concepts)
        
        # Must have minimum concepts
        if len(concepts) >= MIN_CONCEPTS_PER_REQUIREMENT:
            requirements.append({
                "requirement": term,
                "concepts": concepts,
                "category": category,
                "experience_level": None,
                "context": None
            })
    
    if debug:
        logger.info(f"Regex extraction found {len(requirements)} requirements")
    
    return requirements[:20]  # Limit to top 20


def enrich_requirements_with_embeddings(requirements: List[Dict]) -> List[str]:
    """
    Create a flattened concept list for embedding-based search.
    Only includes validated, deduplicated concepts.
    
    Args:
        requirements: List of requirement dictionaries
    
    Returns:
        List of unique, valid concepts
    """
    all_concepts = []
    
    for req in requirements:
        # Add all concepts (already cleaned)
        concepts = req.get("concepts", [])
        if isinstance(concepts, list):
            all_concepts.extend(concepts)
    
    # Final deduplication (case-insensitive)
    unique_concepts = _clean_and_deduplicate_concepts(all_concepts)
    
    return unique_concepts


def validate_requirements(requirements: List[Dict]) -> bool:
    """
    Validate the structure and quality of extracted requirements.
    
    Returns:
        True if requirements are valid and high-quality, False otherwise
    """
    if not requirements or not isinstance(requirements, list):
        return False
    
    if len(requirements) == 0:
        return False
  
    valid_count = 0
    for req in requirements:
        if not isinstance(req, dict):
            continue
        
        # Check structure
        if "requirement" not in req or "concepts" not in req:
            continue
        
        # Validate requirement
        requirement = req["requirement"]
        if not _is_valid_concept(requirement):
            continue
        
        # Validate concepts
        concepts = req["concepts"]
        if not isinstance(concepts, list) or len(concepts) < MIN_CONCEPTS_PER_REQUIREMENT:
            continue
        
        # Check concepts are valid
        valid_concepts = sum(1 for c in concepts if _is_valid_concept(c))
        if valid_concepts < MIN_CONCEPTS_PER_REQUIREMENT:
            continue
        
        valid_count += 1
    
    # At least 70% must be valid
    return (valid_count / len(requirements)) >= 0.7


def get_requirement_summary(requirements: List[Dict]) -> Dict:
    """
    Generate summary statistics for extracted requirements.
    """
    if not requirements:
        return {
            "total_requirements": 0,
            "total_concepts": 0,
            "unique_concepts": 0,
            "avg_concepts_per_req": 0,
            "categories": {},
            "validation_passed": False
        }
    
    total_concepts = sum(len(req.get("concepts", [])) for req in requirements)
    
    # Count unique concepts
    all_concepts = []
    for req in requirements:
        all_concepts.extend(req.get("concepts", []))
    unique_concepts = len(set(all_concepts))
    
    # Category breakdown
    categories = {}
    for req in requirements:
        cat = req.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
    
    return {
        "total_requirements": len(requirements),
        "total_concepts": total_concepts,
        "unique_concepts": unique_concepts,
        "avg_concepts_per_req": round(total_concepts / len(requirements), 1) if requirements else 0,
        "categories": categories,
        "validation_passed": validate_requirements(requirements)
    }