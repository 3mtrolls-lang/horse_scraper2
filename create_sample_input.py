"""
samples/create_sample_input.py
Run this script to create a sample input Excel file for testing.

Usage:
  python samples/create_sample_input.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

SAMPLE_HORSES = [
    "Equinox (JPN)",
    "Forever Young (JPN)",
    "Romantic Warrior (IRE)",
    "Frankel (GB)",
    "Flightline (USA)",
    "Winx (AUS)",
    "Golden Sixty (HK)",
    "Panthalassa (JPN)",
    "Real Impact (JPN)",
    "Ace Impact (FR)",
    "Auguste Rodin (IRE)",
    "National Treasure (GB)",
    "Al Riffa (GB)",
    "Westover (GB)",
]

def create_sample():
    df = pd.DataFrame({"Horse Name": SAMPLE_HORSES})
    out = os.path.join(os.path.dirname(__file__), "sample_horses.xlsx")
    df.to_excel(out, index=False)
    print(f"Sample input created: {out}")
    return out

if __name__ == "__main__":
    create_sample()
