"""
Resume text extraction from PDF files.
Supports both text-based and OCR-based PDFs.
"""

import logging
import re
from typing import Optional, Set

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ===============================
# PDF EXTRACTION
# ===============================

def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    try:
        text = _extract_with_pypdf2(pdf_path)

        if text and len(text.strip()) > 100:
            return text

        logger.info("PyPDF2 extraction yielded insufficient text, trying pdfplumber...")
        text = _extract_with_pdfplumber(pdf_path)

        if text and len(text.strip()) > 100:
            return text

        logger.warning("Standard extraction failed, attempting OCR...")
        text = _extract_with_ocr(pdf_path)

        return text

    except Exception as e:
        logger.error(f"Failed to extract text from {pdf_path}: {e}")
        return None


def _extract_with_pypdf2(pdf_path: str) -> Optional[str]:
    try:
        import PyPDF2

        text_parts = []

        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)

            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

        full_text = '\n\n'.join(text_parts)
        logger.info(f"PyPDF2 extracted {len(full_text)} characters")

        return full_text if full_text.strip() else None

    except ImportError:
        logger.error("PyPDF2 not installed. Run: pip install PyPDF2")
        return None
    except Exception as e:
        logger.error(f"PyPDF2 extraction failed: {e}")
        return None


def _extract_with_pdfplumber(pdf_path: str) -> Optional[str]:
    try:
        import pdfplumber

        text_parts = []

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

        full_text = '\n\n'.join(text_parts)
        logger.info(f"pdfplumber extracted {len(full_text)} characters")

        return full_text if full_text.strip() else None

    except ImportError:
        logger.warning("pdfplumber not installed. pip install pdfplumber")
        return None
    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {e}")
        return None


def _extract_with_ocr(pdf_path: str) -> Optional[str]:
    try:
        import pytesseract
        from pdf2image import convert_from_path

        images = convert_from_path(pdf_path, dpi=300)
        text_parts = []

        for image in images:
            text = pytesseract.image_to_string(image, lang='eng')
            if text:
                text_parts.append(text)

        full_text = '\n\n'.join(text_parts)
        logger.info(f"OCR extracted {len(full_text)} characters")

        return full_text if full_text.strip() else None

    except ImportError:
        logger.error("Install OCR deps: pip install pytesseract pdf2image pillow")
        return None
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return None


# ===============================
# TEXT CLEANING
# ===============================

def clean_text(text: str) -> str:
    if not text:
        return ""

    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]

    cleaned = '\n'.join(lines)
    cleaned = re.sub(r' +', ' ', cleaned)

    return cleaned


def extract_and_clean(pdf_path: str) -> Optional[str]:
    text = extract_text_from_pdf(pdf_path)
    return clean_text(text) if text else None


def extract_resume_text(pdf_path: str) -> str:
    text = extract_and_clean(pdf_path)
    return text if text else ""


# ===============================
# 🔥 ADD THIS FUNCTION (FIX)
# ===============================

def extract_resume_terms(resume_text: str) -> Set[str]:
    """
    Extract clean, meaningful terms from resume text
    for matching logic.
    """

    if not resume_text:
        return set()

    resume_text = resume_text.lower()

    # remove special characters
    resume_text = re.sub(r"[^a-zA-Z0-9\s]", " ", resume_text)

    tokens = resume_text.split()

    # remove very short tokens & stopwords
    stopwords = {
        "the", "and", "for", "with", "this", "that", "have",
        "has", "had", "are", "was", "were", "from", "your",
        "you", "our", "their", "will", "can", "use", "using",
        "we", "in", "on", "of", "to", "a", "an"
    }

    filtered = [
        t for t in tokens
        if len(t) > 2 and t not in stopwords
    ]

    return set(filtered)

import re

def extract_resume_terms(text: str):
    """
    Extract meaningful resume terms for matching.
    """
    if not text:
        return []

    text = text.lower()

    # Remove special characters
    text = re.sub(r'[^a-z0-9\s]', ' ', text)

    # Remove common stopwords
    stopwords = {
        "and", "or", "the", "with", "for", "a", "an", "to",
        "of", "in", "on", "at", "is", "are", "was", "were",
        "we", "i", "my", "our", "your", "their"
    }

    words = [w.strip() for w in text.split() if len(w) > 2 and w not in stopwords]

    return list(set(words))

