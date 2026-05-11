"""
models.py - Data models (dataclasses) for the Horse Racing Scraper.
All scrapers must return RaceRecord instances.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RaceRecord:
    """
    Unified race record — holds both completed race data
    and upcoming entry data for a single horse start.
    """

    # ── Horse identity ──────────────────────────────────────
    horse_name: str = ""          # Clean name, no country code  e.g. "Forever Young"
    country_code: str = ""        # e.g. "JPN", "IRE", "GB"
    age: str = ""                 # e.g. "4"
    sex: str = ""                 # e.g. "C" (colt), "F" (filly), "G" (gelding)

    # ── Race identity ────────────────────────────────────────
    race_date: str = ""           # DD-MM-YYYY
    meeting: str = ""             # Centre name (short code)  e.g. "M" (Meydan)
    race_no: str = ""             # Race number on the day
    race_track: str = ""          # Short track code  e.g. "ST" (Sha Tin)
    race_name: str = ""           # Full race name
    race_value: str = ""          # Prize money  e.g. "£500,000"
    group: str = ""               # G1, G2, G3, L, H, etc.
    surface: str = ""             # T, D, AW
    age_cond: str = ""            # Age condition  e.g. "3yo+"
    other_cond: str = ""          # Other conditions
    distance: str = ""            # e.g. "1200m", "1m2f"
    starters: str = ""            # Number of runners
    race_status: str = ""         # COMPLETED / UPCOMING

    # ── Result / placing ─────────────────────────────────────
    placing: str = ""             # "1st", "2nd", etc.  (text form)
    placing2: str = ""            # Numeric only  "1", "2", etc.
    position: str = ""            # same as placing2 sometimes

    # ── Horse number & draw ──────────────────────────────────
    h_no: str = ""                # Horse / saddle cloth number
    d_no: str = ""                # Draw / barrier number
    h_d: str = ""                 # Combined: "3[5]"

    # ── Weight ───────────────────────────────────────────────
    weight_allotted: str = ""     # kg
    weight_carried: str = ""      # kg (falls back to allotted if missing)
    wt: str = ""                  # raw weight field

    # ── Jockey ───────────────────────────────────────────────
    jockey_name: str = ""         # Full jockey name (primary)
    jockey: str = ""              # Duplicate column as per spec

    # ── Lengths beaten ───────────────────────────────────────
    btn_by: str = ""              # Beaten by / Btn
    len: str = ""                 # Lengths

    # ── Ratings ──────────────────────────────────────────────
    pre_rating_official: str = ""
    post_rating_official: str = ""
    turf_rating: str = ""
    pf: str = ""                  # Performance figure

    # ── Comments ─────────────────────────────────────────────
    handicapper_comments: str = ""  # HC
    hc: str = ""                    # short alias
    stewards_comments: str = ""     # SC
    sc: str = ""                    # short alias

    # ── Equipment ────────────────────────────────────────────
    equipment: str = ""           # Full names  e.g. "Blinkers; Tongue Strap"
    equip2: str = ""              # Short codes e.g. "B; TS"

    # ── Centre/Track composite ───────────────────────────────
    c_t: str = ""                 # Centre(Track)  e.g. "M(T)"

    # ── Time ─────────────────────────────────────────────────
    time: str = ""                # Race time / finishing time

    # ── Source metadata ──────────────────────────────────────
    source_url: str = ""
    scraper_name: str = ""

    def to_dict(self) -> dict:
        """
        Convert the dataclass to a flat dict using the exact Excel column names.
        """
        return {
            "Horse Name":             self.horse_name,
            "Placing":                self.placing,
            "WeightAllotted":         self.weight_allotted,
            "WeightCarried":          self.weight_carried,
            "Len":                    self.len,
            "JockeyName":             self.jockey_name,
            "Pre_Rating_Official":    self.pre_rating_official,
            "Post_Rating_Official":   self.post_rating_official,
            "Turf Rating":            self.turf_rating,
            "PF":                     self.pf,
            "Handicapper Comments":   self.handicapper_comments or self.hc,
            "RaceDate":               self.race_date,
            "Meeting":                self.meeting,
            "RaceNo":                 self.race_no,
            "RaceTrack":              self.race_track,
            "RaceName":               self.race_name,
            "RaceValue":              self.race_value,
            "Group":                  self.group,
            "Surface":                self.surface,
            "AgeCond":                self.age_cond,
            "OtherCond":              self.other_cond,
            "Distance":               self.distance,
            "Starters":               self.starters,
            "Time":                   self.time,
            "StewardsComments":       self.stewards_comments or self.sc,
            "H No":                   self.h_no,
            "D No":                   self.d_no,
            "Btn/Btn by":             self.btn_by,
            "Age":                    self.age,
            "Sex":                    self.sex,
            "Position":               self.position or self.placing2,
            "Jockey":                 self.jockey or self.jockey_name,
            "Equipment":              self.equipment,
            "H[D]":                   self.h_d,
            "C(T)":                   self.c_t,
            "Wt":                     self.wt or self.weight_carried or self.weight_allotted,
            "Placing2":               self.placing2,
            "HC":                     self.hc or self.handicapper_comments,
            "SC":                     self.sc or self.stewards_comments,
            "Equip2":                 self.equip2,
            "CountryCode":            self.country_code,
            "RaceStatus":             self.race_status,
            "SourceURL":              self.source_url,
        }


@dataclass
class HorseInput:
    """
    Parsed input record for a single horse.
    """
    raw_name: str                 # Original string e.g. "Forever Young (JPN)"
    clean_name: str               # e.g. "Forever Young"
    country_code: str = ""        # e.g. "JPN"
    scraper_priority: list = field(default_factory=list)
