# normalize.py
import re
from typing import Tuple

# Minimal ruleset to start. Expand with fuzzy matching or use textsearch libs (fuzzywuzzy, RapidFuzz).
NORMALIZATION_RULES = [
    (r'\bwhole milk\b', 'milk, whole'),
    (r'\b2% milk\b|\bwhole milk\b|\bskim milk\b|\b1% milk\b', 'milk'),
    (r'\bread[- ]?berry\b', 'strawberries'),  # example
    (r'\bbananas\b|\bbanana\b', 'banana'),
    (r'\bapple\b|\bapples\b', 'apple'),
    (r'\bground beef\b', 'ground beef'),
]

def canonicalize(raw_name: str) -> str:
    s = raw_name.lower()
    s = re.sub(r'[^a-z0-9\s%./-]', ' ', s)  # drop special chars
    s = re.sub(r'\s+', ' ', s).strip()

    for pattern, canonical in NORMALIZATION_RULES:
        if re.search(pattern, s):
            return canonical
    # fallback: use first two words
    words = s.split()
    return ' '.join(words[:2]) if words else s

def parse_unit_and_qty(raw_name: str) -> Tuple[str, float]:
    """
    Very simple extractor: looks for '1 lb', '2 lb', '16 oz', 'gallon', etc.
    Returns unit string and quantity as float whenever possible.
    """
    s = raw_name.lower()
    m = re.search(r'(\d+(\.\d+)?)\s*(g|kg|lb|oz|fl oz|l|ml|gallon|gal)', s)
    if m:
        qty = float(m.group(1))
        unit = m.group(3)
        return unit, qty
    # fallback
    if 'gallon' in s or 'gal' in s:
        return 'gal', 1.0
    return '', 0.0
