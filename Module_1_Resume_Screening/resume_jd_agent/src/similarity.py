"""
Production-ready semantic similarity with multiple backend options.

Supports:
1. OpenAI API (recommended for production)
2. Lightweight local embedding (fastembed - no torch dependency)
3. Sentence-transformers (fallback, heavy)

Configure via environment variable: EMBEDDING_BACKEND
"""

import os
import numpy as np
from typing import List, Union, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "openai")  # openai|fastembed|sentence-transformers
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Lazy loading of backends
_model = None
_openai_client = None


def _init_openai():
    """Initialize OpenAI client for embeddings."""
    global _openai_client
    
    if _openai_client is None:
        try:
            from openai import OpenAI
            
            if not OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not set in environment")
            
            _openai_client = OpenAI(api_key=OPENAI_API_KEY)
            logger.info("OpenAI embedding client initialized")
            
        except ImportError:
            raise ImportError("OpenAI package not installed. Run: pip install openai")
    
    return _openai_client


def _init_fastembed():
    """Initialize FastEmbed (lightweight, no torch, ONNX-based)."""
    global _model
    
    if _model is None:
        try:
            from fastembed import TextEmbedding
            
            # Use BAAI/bge-small-en-v1.5 - fast, lightweight, good quality
            _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            logger.info("FastEmbed model initialized (BAAI/bge-small-en-v1.5)")
            
        except ImportError:
            raise ImportError(
                "FastEmbed not installed. Run: pip install fastembed\n"
                "FastEmbed is lightweight (~50MB) and has no torch dependency."
            )
    
    return _model


def _init_sentence_transformers():
    """Initialize sentence-transformers (heavy, torch dependency)."""
    global _model
    
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            
            _model = SentenceTransformer('all-MiniLM-L6-v2')  # Smaller than mpnet
            logger.warning(
                "Using sentence-transformers backend. "
                "This is heavy and may cause deployment issues. "
                "Consider using 'openai' or 'fastembed' backend."
            )
            
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. Run: pip install sentence-transformers\n"
                "WARNING: This is heavy. Consider using 'openai' or 'fastembed' instead."
            )
    
    return _model


def get_embeddings(texts: Union[str, List[str]], backend: Optional[str] = None) -> np.ndarray:
    """
    Get embeddings for text(s) using configured backend.
    
    Args:
        texts: Single text or list of texts
        backend: Override default backend (openai|fastembed|sentence-transformers)
    
    Returns:
        numpy array of embeddings (1D for single text, 2D for list)
    """
    if backend is None:
        backend = EMBEDDING_BACKEND
    
    # Normalize input
    is_single = isinstance(texts, str)
    if is_single:
        texts = [texts]
    
    # Filter empty texts
    texts = [t.strip() for t in texts if t and t.strip()]
    if not texts:
        return np.array([])
    
    # Get embeddings based on backend
    if backend == "openai":
        embeddings = _get_openai_embeddings(texts)
    elif backend == "fastembed":
        embeddings = _get_fastembed_embeddings(texts)
    elif backend == "sentence-transformers":
        embeddings = _get_sentence_transformer_embeddings(texts)
    else:
        raise ValueError(f"Unknown backend: {backend}. Use: openai, fastembed, or sentence-transformers")
    
    # Return format based on input
    if is_single:
        return embeddings[0]
    return embeddings


def _get_openai_embeddings(texts: List[str]) -> np.ndarray:
    """Get embeddings using OpenAI API."""
    client = _init_openai()
    
    try:
        # OpenAI supports batch embedding
        response = client.embeddings.create(
            model="text-embedding-3-small",  # Fast, cheap, good quality
            input=texts
        )
        
        embeddings = np.array([item.embedding for item in response.data])
        return embeddings
        
    except Exception as e:
        logger.error(f"OpenAI embedding failed: {e}")
        raise


def _get_fastembed_embeddings(texts: List[str]) -> np.ndarray:
    """Get embeddings using FastEmbed (lightweight, ONNX)."""
    model = _init_fastembed()
    
    try:
        # FastEmbed returns generator
        embeddings = list(model.embed(texts))
        return np.array(embeddings)
        
    except Exception as e:
        logger.error(f"FastEmbed embedding failed: {e}")
        raise


def _get_sentence_transformer_embeddings(texts: List[str]) -> np.ndarray:
    """Get embeddings using sentence-transformers (heavy)."""
    model = _init_sentence_transformers()
    
    try:
        embeddings = model.encode(texts, convert_to_numpy=True)
        return embeddings
        
    except Exception as e:
        logger.error(f"Sentence-transformers embedding failed: {e}")
        raise


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Args:
        vec1: First embedding vector
        vec2: Second embedding vector
    
    Returns:
        Similarity score between -1 and 1 (typically 0 to 1)
    """
    # Normalize vectors
    vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-10)
    vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-10)
    
    # Compute cosine similarity
    similarity = np.dot(vec1_norm, vec2_norm)
    
    return float(similarity)


def semantic_similarity(text1: str, text2: str, backend: Optional[str] = None) -> float:
    """
    Calculate semantic similarity between two texts.
    
    Args:
        text1: First text
        text2: Second text
        backend: Override default backend
    
    Returns:
        Similarity score between 0 and 1
    """
    if not text1 or not text2:
        return 0.0
    
    # Clean texts
    text1 = text1.strip()
    text2 = text2.strip()
    
    if not text1 or not text2:
        return 0.0
    
    # For very short texts, direct comparison
    if len(text1) < 50 or len(text2) < 50:
        embeddings = get_embeddings([text1, text2], backend=backend)
        return cosine_similarity(embeddings[0], embeddings[1])
    
    # For longer texts, use chunking for better accuracy
    chunks1 = chunk_text(text1, max_length=500)
    chunks2 = chunk_text(text2, max_length=500)
    
    # Get embeddings for all chunks
    all_texts = chunks1 + chunks2
    embeddings = get_embeddings(all_texts, backend=backend)
    
    # Split back into chunk groups
    emb1 = embeddings[:len(chunks1)]
    emb2 = embeddings[len(chunks1):]
    
    # Calculate max similarity across chunks
    max_sims = []
    for e1 in emb1:
        chunk_sims = [cosine_similarity(e1, e2) for e2 in emb2]
        max_sims.append(max(chunk_sims))
    
    # Return average of top similarities
    return float(np.mean(max_sims))


def batch_semantic_similarity(
    query: str,
    candidates: List[str],
    backend: Optional[str] = None,
    top_k: Optional[int] = None
) -> List[tuple]:
    """
    Calculate similarity between query and multiple candidates efficiently.
    
    Args:
        query: Query text
        candidates: List of candidate texts
        backend: Override default backend
        top_k: Return only top K results (sorted by similarity)
    
    Returns:
        List of (index, similarity) tuples, optionally limited to top_k
    """
    if not query or not candidates:
        return []
    
    # Get all embeddings in one batch
    all_texts = [query] + candidates
    embeddings = get_embeddings(all_texts, backend=backend)
    
    query_emb = embeddings[0]
    candidate_embs = embeddings[1:]
    
    # Calculate similarities
    similarities = []
    for idx, cand_emb in enumerate(candidate_embs):
        sim = cosine_similarity(query_emb, cand_emb)
        similarities.append((idx, sim))
    
    # Sort by similarity (descending)
    similarities.sort(key=lambda x: x[1], reverse=True)
    
    # Return top_k if specified
    if top_k is not None:
        similarities = similarities[:top_k]
    
    return similarities


def chunk_text(text: str, max_length: int = 500, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Text to chunk
        max_length: Maximum words per chunk
        overlap: Number of overlapping words between chunks
    
    Returns:
        List of text chunks
    """
    words = text.split()
    
    if len(words) <= max_length:
        return [text]
    
    chunks = []
    for i in range(0, len(words), max_length - overlap):
        chunk = ' '.join(words[i:i + max_length])
        if chunk.strip():
            chunks.append(chunk)
    
    return chunks if chunks else [text]


def get_backend_info() -> dict:
    """
    Get information about current backend configuration.
    
    Returns:
        Dictionary with backend info and recommendations
    """
    info = {
        "current_backend": EMBEDDING_BACKEND,
        "backends": {
            "openai": {
                "available": bool(OPENAI_API_KEY),
                "pros": ["Fast", "No local resources", "High quality", "Production-ready"],
                "cons": ["Requires API key", "Costs money", "Network dependency"],
                "recommended_for": "Production deployment"
            },
            "fastembed": {
                "available": True,
                "pros": ["Lightweight (~50MB)", "No torch", "ONNX-based", "Free", "Fast"],
                "cons": ["Slightly lower quality than OpenAI", "Local compute"],
                "recommended_for": "Local deployment, Docker, Streamlit"
            },
            "sentence-transformers": {
                "available": True,
                "pros": ["High quality", "Many models available"],
                "cons": ["Heavy (~500MB+)", "Torch dependency", "DLL issues on Windows", "Slow startup"],
                "recommended_for": "Development only (NOT production)"
            }
        }
    }
    
    # Add warnings
    warnings = []
    if EMBEDDING_BACKEND == "sentence-transformers":
        warnings.append(
            "⚠️  sentence-transformers is heavy and causes deployment issues. "
            "Switch to 'openai' or 'fastembed' for production."
        )
    
    if EMBEDDING_BACKEND == "openai" and not OPENAI_API_KEY:
        warnings.append(
            "⚠️  OpenAI backend selected but OPENAI_API_KEY not set. "
            "Set environment variable or switch to 'fastembed'."
        )
    
    info["warnings"] = warnings
    
    return info


# Convenience function to print backend info
def print_backend_info():
    """Print backend configuration and recommendations."""
    info = get_backend_info()
    
    print(f"\n{'='*60}")
    print(f"EMBEDDING BACKEND CONFIGURATION")
    print(f"{'='*60}")
    print(f"\nCurrent backend: {info['current_backend']}")
    
    for backend, details in info['backends'].items():
        marker = "✓" if backend == info['current_backend'] else " "
        available = "✓" if details['available'] else "✗"
        print(f"\n[{marker}] {backend.upper()} (Available: {available})")
        print(f"    Pros: {', '.join(details['pros'])}")
        print(f"    Cons: {', '.join(details['cons'])}")
        print(f"    Best for: {details['recommended_for']}")
    
    if info['warnings']:
        print(f"\n{'='*60}")
        print("WARNINGS:")
        for warning in info['warnings']:
            print(f"  {warning}")
    
    print(f"\n{'='*60}")
    print("\nTo change backend, set environment variable:")
    print("  export EMBEDDING_BACKEND=openai")
    print("  export EMBEDDING_BACKEND=fastembed")
    print("  export EMBEDDING_BACKEND=sentence-transformers")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    # Test and show configuration
    print_backend_info()
    
    # Example usage
    print("\nExample usage:")
    print("-" * 60)
    
    text1 = "Python programming with machine learning"
    text2 = "ML development using Python"
    
    try:
        similarity = semantic_similarity(text1, text2)
        print(f"\nText 1: {text1}")
        print(f"Text 2: {text2}")
        print(f"Similarity: {similarity:.4f}")
        print(f"\nBackend used: {EMBEDDING_BACKEND}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTry setting EMBEDDING_BACKEND and required credentials.")