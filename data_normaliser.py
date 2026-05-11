"""
scrapers/data_normaliser.py
Shared helper functions for normalising scraped data into RaceRecord fields.
All scrapers should import from here rather than duplicate logic.
"""

import re
from datetime import datetime
from typing import Optional

from config import (
    TRACK_CODE_MAP,
    EQUIPMENT_CODE_MAP,
    GROUP_MAP,
    PLACING_TEXT_MAP,
    DATE_FORMAT,
    SURFACE_MAP,
)
from weight_utils import normalise_weight


# ─── Date parsing ─────────────────────────────────────────────

_DATE_PATTERNS = [
    "%d %B %Y",       # 12 April 2024
    "%d %b %Y",       # 12 Apr 2024
    "%B %d, %Y",      # April 12, 2024
    "%b %d, %Y",      # Apr 12, 2024
    "%Y-%m-%d",       # 2024-04-12
    "%d/%m/%Y",       # 12/04/2024
    "%m/%d/%Y",       # 04/12/2024
    "%d-%m-%Y",       # 12-04-2024
    "%d.%m.%Y",       # 12.04.2024
    "%Y/%m/%d",       # 2024/04/12
    "%d %b %y",       # 12 Apr 24
]


def normalise_date(raw: str) -> str:
    """
    Parse a raw date string and return in DD-MM-YYYY format.
    Returns raw string unchanged if no pattern matches.
    """
    if not raw:
        return ""
    raw = raw.strip()
    # Remove ordinal suffixes: "12th" → "12"
    raw = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", raw, flags=re.IGNORECASE)
    for fmt in _DATE_PATTERNS:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime(DATE_FORMAT)
        except ValueError:
            continue
    return raw   # Return as-is if unparseable


# ─── Track code ───────────────────────────────────────────────

def get_track_code(track_name: str) -> str:
    """
    Return the short code for a racecourse name.
    Falls back to the first 3 uppercase letters if not in map.
    """
    if not track_name:
        return ""
    lower = track_name.lower().strip()
    # Exact match
    if lower in TRACK_CODE_MAP:
        return TRACK_CODE_MAP[lower]
    # Partial match (substring)
    for key, code in TRACK_CODE_MAP.items():
        if key in lower or lower in key:
            return code
    # Generate a fallback code
    words = track_name.upper().split()
    return "".join(w[0] for w in words)[:4]


# ─── Group normalisation ──────────────────────────────────────

def normalise_group(raw: str) -> str:
    """Return a standard group code from a raw string."""
    if not raw:
        return ""
    lower = raw.lower().strip()
    for key, code in GROUP_MAP.items():
        if key in lower:
            return code
    return raw.strip()


# ─── Surface normalisation ────────────────────────────────────

def normalise_surface(raw: str) -> str:
    """Return T / D / AW from a surface description."""
    if not raw:
        return ""
    lower = raw.lower().strip()
    for key, code in SURFACE_MAP.items():
        if key in lower:
            return code
    return raw[:2].upper()


# ─── Placing normalisation ────────────────────────────────────

def normalise_placing(raw: str) -> tuple[str, str]:
    """
    Return (placing_text, placing_numeric).
    e.g. "1st" → ("1st", "1")
         "5"   → ("5th", "5")
         "PU"  → ("PU", "PU")
    """
    if not raw:
        return "", ""
    raw = str(raw).strip()
    lower = raw.lower()

    # Direct map
    if lower in PLACING_TEXT_MAP:
        num = PLACING_TEXT_MAP[lower]
        text = _ordinal(num) if num.isdigit() else num
        return text, num

    # Already a number
    if raw.isdigit():
        n = int(raw)
        return _ordinal(str(n)), str(n)

    # Strip ordinal suffix to get number
    num_match = re.match(r"^(\d+)(?:st|nd|rd|th)$", lower)
    if num_match:
        n = num_match.group(1)
        return _ordinal(n), n

    return raw, raw


def _ordinal(n: str) -> str:
    """Return ordinal string: "1" → "1st", "2" → "2nd", etc."""
    try:
        i = int(n)
        if 10 <= i % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(i % 10, "th")
        return f"{i}{suffix}"
    except ValueError:
        return n


# ─── Equipment normalisation ──────────────────────────────────

def normalise_equipment(raw: str) -> tuple[str, str]:
    """
    Return (full_equipment_string, short_code_string).
    e.g. "Blinkers; Tongue Strap" → ("Blinkers; Tongue Strap", "B; TS")
    """
    if not raw:
        return "", ""

    parts = [p.strip() for p in re.split(r"[;,/]", raw) if p.strip()]
    full_parts = []
    code_parts = []
    for part in parts:
        lower = part.lower()
        # Find matching key in equipment map
        matched_key = None
        for key in EQUIPMENT_CODE_MAP:
            if key in lower or lower in key:
                matched_key = key
                break
        if matched_key:
            full_parts.append(matched_key.title())
            code = EQUIPMENT_CODE_MAP[matched_key]
            if code:
                code_parts.append(code)
        else:
            full_parts.append(part.title())
            # Generate abbreviation from first letters of each word
            abbrev = "".join(w[0].upper() for w in part.split())
            if abbrev:
                code_parts.append(abbrev)

    return "; ".join(full_parts), "; ".join(code_parts)


# ─── Centre(Track) composite ─────────────────────────────────

def build_c_t(centre: str, surface: str) -> str:
    """
    Build C(T) field: Centre(Track type).
    e.g. centre="Meydan" surface="T" → "M(T)"
    """
    centre_code = get_track_code(centre)
    surf_code = normalise_surface(surface)
    if centre_code and surf_code:
        return f"{centre_code}({surf_code})"
    return centre_code or ""


# ─── H[D] composite ──────────────────────────────────────────

def build_h_d(h_no: str, d_no: str) -> str:
    """
    Build H[D] field: Horse No [Draw No].
    e.g. h_no="3" d_no="5" → "3[5]"
    """
    if h_no and d_no:
        return f"{h_no}[{d_no}]"
    return h_no or d_no or ""


# ─── Distance normalisation ───────────────────────────────────

def normalise_distance(raw: str) -> str:
    """
    Normalise distance to a readable format.
    Tries to convert furlongs to metres when obvious.
    """
    if not raw:
        return ""
    raw = raw.strip()
    # Furlong format: "6f", "1m2f", "1m 2f 110y"
    # Leave as-is — just clean whitespace
    return re.sub(r"\s+", " ", raw)
