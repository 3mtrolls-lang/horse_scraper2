"""
weight_utils.py - Weight conversion and normalisation utilities.

Horse racing weights are expressed in many formats:
  Stones-Pounds:  "9-2"  (9 stones 2 pounds)
  Pounds only:    "126"  or "126lb"
  Kilograms:      "57.5" or "57.5kg"

All weights are converted to kilograms (2dp).
"""

import re
from typing import Optional

# 1 stone = 14 pounds; 1 pound = 0.453592 kg
_POUNDS_PER_STONE = 14
_KG_PER_POUND = 0.453592


def stones_pounds_to_kg(stones: int, pounds: int) -> float:
    """Convert stones + pounds to kilograms."""
    total_pounds = stones * _POUNDS_PER_STONE + pounds
    return round(total_pounds * _KG_PER_POUND, 2)


def pounds_to_kg(pounds: float) -> float:
    """Convert pounds to kilograms."""
    return round(pounds * _KG_PER_POUND, 2)


def parse_weight(raw: str) -> Optional[str]:
    """
    Parse a raw weight string and return kilograms as a formatted string.

    Handles:
      "9-2"       → stones-pounds
      "9st 2lb"   → stones-pounds
      "126"       → raw pounds (if > 30, assumed pounds)
      "126lb"     → explicit pounds
      "57.5kg"    → already kilograms
      "57.5"      → already kg if ≤ 99 and contains decimal
      ""          → None (blank)
    """
    if not raw or not str(raw).strip():
        return None

    raw = str(raw).strip().lower()

    # Already in kg explicitly
    kg_match = re.match(r"^(\d+(?:\.\d+)?)\s*kg$", raw)
    if kg_match:
        return str(round(float(kg_match.group(1)), 2))

    # Stones-pounds: "9-2" or "9st 2lb" or "9st2lb"
    st_lb_match = re.match(r"^(\d+)\s*(?:st|stone|-)?\s*[-\s]?\s*(\d+)\s*(?:lb|lbs|pounds?)?$", raw)
    if st_lb_match:
        stones = int(st_lb_match.group(1))
        lbs = int(st_lb_match.group(2))
        # Sanity: stones 5-20 range typical for racehorses
        if 5 <= stones <= 20:
            return str(stones_pounds_to_kg(stones, lbs))

    # Pure pounds with suffix
    lbs_match = re.match(r"^(\d+(?:\.\d+)?)\s*(?:lb|lbs|pounds?)$", raw)
    if lbs_match:
        lbs = float(lbs_match.group(1))
        return str(pounds_to_kg(lbs))

    # Pure number — heuristic:
    #   If float and value ≤ 99  → already kg
    #   If integer and value > 30 → pounds
    num_match = re.match(r"^(\d+(?:\.\d+)?)$", raw)
    if num_match:
        val = float(num_match.group(1))
        if "." in raw and val <= 99:
            # Assume kg
            return str(round(val, 2))
        elif val > 30:
            # Assume pounds
            return str(pounds_to_kg(val))
        else:
            # Small integer — could be stones with no pounds part (e.g. "9" = 9st 0lb)
            return str(stones_pounds_to_kg(int(val), 0))

    # Could not parse
    return None


def normalise_weight(raw: str, fallback: Optional[str] = None) -> str:
    """
    Return a clean kg string or fallback or empty string.
    """
    result = parse_weight(raw)
    if result:
        return result
    if fallback:
        result2 = parse_weight(fallback)
        if result2:
            return result2
    return ""


# ─── Quick tests (run directly) ──────────────────────────────
if __name__ == "__main__":
    tests = [
        ("9-2", "57.15"),
        ("8-11", "56.25"),
        ("126", "57.15"),
        ("126lb", "57.15"),
        ("57.5kg", "57.5"),
        ("57.5", "57.5"),
        ("10-0", "63.5"),
        ("", None),
    ]
    for raw, expected in tests:
        result = parse_weight(raw)
        status = "✓" if (result == expected or (result is None and expected is None)) else "✗"
        print(f"{status}  parse_weight({raw!r}) = {result!r}  (expected {expected!r})")
