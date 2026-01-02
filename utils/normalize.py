# normalize.py
import re
from typing import Tuple, List
from rapidfuzz import fuzz  # Add to requirements.txt

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

# Unit conversion mappings
UNIT_CONVERSIONS = {
    'gal': 'gallon',
    'fl oz': 'oz',
    'l': 'liter',
    'ml': 'milliliter',
    'kg': 'kilogram',
    'g': 'gram',
}

# Normalization rules (expand as needed)
NORMALIZATION_RULES = [
    # Milk variants - normalize all to just "milk"
    (r'\bmilk\b', 'milk'),  # Catches "whole milk", "2% milk", "milk", etc.

    # Eggs
    (r'\beggs?\b', 'eggs'),  # Catches "egg", "eggs", "large eggs", etc.

    # Bananas
    (r'\bbananas?\b', 'banana'),

    # Apples
    (r'\bapples?\b', 'apple'),

    # Strawberries
    (r'\bread[- ]?berr(?:y|ies)\b', 'strawberries'),

    # Ground beef
    (r'\bground beef\b', 'ground beef'),
]

# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def canonicalize(raw_name: str) -> Tuple[str, float]:
    """
    Convert raw product name to canonical name with confidence score.

    Args:
        raw_name: Raw product name from store data

    Returns:
        Tuple of (canonical_name, confidence_score)
        - confidence_score: 1.0 for rule match, 0.5 for fallback
    """
    s = raw_name.lower()
    s = re.sub(r'[^a-z0-9\s%./-]', ' ', s)  # drop special chars
    s = re.sub(r'\s+', ' ', s).strip()

    # Try to match against rules
    for pattern, canonical in NORMALIZATION_RULES:
        if re.search(pattern, s):
            return canonical, 1.0  # High confidence - matched a rule

    # Fallback: use first two words
    words = s.split()
    fallback = ' '.join(words[:2]) if words else s
    return fallback, 0.5  # Lower confidence - using fallback


def parse_unit_and_qty(raw_name: str) -> Tuple[str, float]:
    """
    Extract unit and quantity from raw product name.

    Args:
        raw_name: Raw product name from store data

    Returns:
        Tuple of (unit, quantity)
        - unit: Normalized unit string (e.g., 'lb', 'oz', 'gallon')
        - quantity: Numeric quantity as float
    """
    s = raw_name.lower()
    m = re.search(r'(\d+(\.\d+)?)\s*(g|kg|lb|oz|fl oz|l|ml|gallon|gal)', s)
    if m:
        qty = float(m.group(1))
        unit = m.group(3)
        return normalize_unit(unit), qty

    # Fallback for common units without explicit quantity
    if 'gallon' in s or 'gal' in s:
        return 'gallon', 1.0

    return '', 0.0


def normalize_unit(unit: str) -> str:
    """
    Standardize unit names to consistent format.

    Args:
        unit: Raw unit string

    Returns:
        Normalized unit string
    """
    return UNIT_CONVERSIONS.get(unit.lower(), unit.lower())


def find_similar_canonical(raw_name: str, existing_products: List[str],
                          threshold: float = 0.8) -> Tuple[str, float]:
    """
    Find most similar existing canonical product using fuzzy matching.

    Args:
        raw_name: Raw product name to match
        existing_products: List of existing canonical product names
        threshold: Minimum similarity score (0-1) to consider a match

    Returns:
        Tuple of (best_match, confidence_score)
        - best_match: Most similar canonical name, or None if below threshold
        - confidence_score: Similarity score (0-1)
    """
    if not existing_products:
        return None, 0.0

    best_match = None
    best_score = 0.0

    for product in existing_products:
        score = fuzz.ratio(raw_name.lower(), product.lower())
        if score > best_score:
            best_score = score
            best_match = product

    # Convert to 0-1 range and check threshold
    confidence = best_score / 100.0
    if confidence < threshold:
        return None, confidence

    return best_match, confidence
