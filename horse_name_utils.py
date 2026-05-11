"""
horse_name_utils.py - Utilities for parsing, normalising, and fuzzy-matching horse names.
"""

import re
import unicodedata
from typing import Optional

try:
    from rapidfuzz import fuzz, process as rfuzz_process
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

from config import FUZZY_MATCH_THRESHOLD


# ─────────────────────────────────────────────────────────────
# REGEX: extract country code from e.g. "Forever Young (JPN)"
# ─────────────────────────────────────────────────────────────
_COUNTRY_RE = re.compile(r"\(([A-Z]{2,4})\)\s*$")


def parse_horse_name(raw: str) -> tuple[str, str]:
    """
    Parse a raw horse name string.

    Returns:
        (clean_name, country_code)
        e.g. ("Forever Young", "JPN")
             ("Romantic Warrior", "IRE")
             ("Secretariat", "")
    """
    raw = raw.strip()
    match = _COUNTRY_RE.search(raw)
    if match:
        country_code = match.group(1).upper()
        clean_name = raw[: match.start()].strip()
    else:
        country_code = ""
        clean_name = raw

    # Remove any remaining parentheses groups
    clean_name = re.sub(r"\([^)]*\)", "", clean_name).strip()
    return clean_name, country_code


def normalise_name(name: str) -> str:
    """
    Normalise a horse name for comparison:
    - Strip accents/diacritics
    - Lowercase
    - Remove punctuation except hyphens
    - Collapse whitespace
    """
    # NFD decomposition + strip combining characters (accents)
    nfd = unicodedata.normalize("NFD", name)
    without_accents = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    # Lowercase
    lower = without_accents.lower()
    # Remove apostrophes, dots; keep hyphens and spaces
    cleaned = re.sub(r"[^\w\s\-]", "", lower)
    # Collapse whitespace
    collapsed = re.sub(r"\s+", " ", cleaned).strip()
    return collapsed


def fuzzy_match_name(
    query: str,
    candidates: list[str],
    threshold: int = FUZZY_MATCH_THRESHOLD,
) -> Optional[str]:
    """
    Find the best fuzzy match for `query` among `candidates`.

    Returns the best matching candidate or None if below threshold.
    Uses rapidfuzz if available, otherwise falls back to SequenceMatcher.
    """
    if not candidates:
        return None

    norm_query = normalise_name(query)
    norm_candidates = {c: normalise_name(c) for c in candidates}

    if HAS_RAPIDFUZZ:
        # rapidfuzz returns (match, score, index)
        result = rfuzz_process.extractOne(
            norm_query,
            list(norm_candidates.values()),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold,
        )
        if result is None:
            return None
        matched_norm = result[0]
        # Reverse map from normalised back to original
        for orig, norm in norm_candidates.items():
            if norm == matched_norm:
                return orig
        return None
    else:
        # Fallback: Python difflib
        from difflib import SequenceMatcher

        best_score = 0
        best_candidate = None
        for orig, norm in norm_candidates.items():
            score = SequenceMatcher(None, norm_query, norm).ratio() * 100
            if score > best_score:
                best_score = score
                best_candidate = orig

        if best_score >= threshold:
            return best_candidate
        return None


def is_same_horse(name_a: str, name_b: str, threshold: int = FUZZY_MATCH_THRESHOLD) -> bool:
    """
    Check if two horse names refer to the same horse.
    """
    norm_a = normalise_name(name_a)
    norm_b = normalise_name(name_b)

    if norm_a == norm_b:
        return True

    if HAS_RAPIDFUZZ:
        score = fuzz.token_sort_ratio(norm_a, norm_b)
    else:
        from difflib import SequenceMatcher
        score = SequenceMatcher(None, norm_a, norm_b).ratio() * 100

    return score >= threshold


def deduplicate_horses(names: list[str]) -> list[str]:
    """
    Remove duplicate horse names (case-insensitive, fuzzy).
    Preserves first occurrence.
    """
    seen: list[str] = []
    for name in names:
        if not any(is_same_horse(name, s) for s in seen):
            seen.append(name)
    return seen


def build_search_query(horse_name: str, country_code: str = "") -> str:
    """
    Build a search query string for search engines / site search boxes.
    """
    if country_code:
        return f"{horse_name} {country_code} horse racing"
    return f"{horse_name} horse racing"
