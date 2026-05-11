"""
config.py - Central configuration for the Horse Racing Scraper
All constants, mappings, and settings live here.
"""

import os

# ─────────────────────────────────────────────
# DIRECTORY STRUCTURE
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
CACHE_DIR = os.path.join(BASE_DIR, "cache")
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")

for _dir in [OUTPUT_DIR, LOGS_DIR, CACHE_DIR, SAMPLES_DIR]:
    os.makedirs(_dir, exist_ok=True)

# ─────────────────────────────────────────────
# SCRAPER SETTINGS
# ─────────────────────────────────────────────
REQUEST_TIMEOUT = 30          # seconds
MAX_RETRIES = 3
RETRY_WAIT_MIN = 2            # seconds
RETRY_WAIT_MAX = 6
RANDOM_DELAY_MIN = 1.5        # seconds between requests
RANDOM_DELAY_MAX = 4.0
MAX_WORKERS = 4               # ThreadPoolExecutor workers
CACHE_TTL_HOURS = 24          # How long to cache responses

# ─────────────────────────────────────────────
# FUZZY MATCH THRESHOLD
# ─────────────────────────────────────────────
FUZZY_MATCH_THRESHOLD = 80    # RapidFuzz score 0-100

# ─────────────────────────────────────────────
# USER AGENTS ROTATION LIST
# ─────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintox; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# ─────────────────────────────────────────────
# COUNTRY CODE → SCRAPER PRIORITY ROUTING
# Key = country code (uppercase), Value = ordered list of scraper keys
# ─────────────────────────────────────────────
COUNTRY_SCRAPER_PRIORITY: dict[str, list[str]] = {
    "JPN": ["jra", "netkeiba", "japanracing", "racingpost", "attheraces"],
    "JP":  ["jra", "netkeiba", "japanracing", "racingpost", "attheraces"],
    "HK":  ["hkjc", "racingpost", "attheraces"],
    "USA": ["equibase", "racingpost", "attheraces"],
    "US":  ["equibase", "racingpost", "attheraces"],
    "GB":  ["racingpost", "britishhorseracing", "attheraces"],
    "UK":  ["racingpost", "britishhorseracing", "attheraces"],
    "IRE": ["racingpost", "hri", "attheraces"],
    "IE":  ["racingpost", "hri", "attheraces"],
    "FR":  ["racingpost", "francegalop", "attheraces"],
    "GER": ["racingpost", "deutschergalopp", "attheraces"],
    "DE":  ["racingpost", "deutschergalopp", "attheraces"],
    "AUS": ["racingpost", "racingaustralia", "racingvictoria", "attheraces"],
    "AU":  ["racingpost", "racingaustralia", "racingvictoria", "attheraces"],
    "UAE": ["racingpost", "emiratesracing", "attheraces"],
    "SAU": ["saudiracing", "racingpost", "attheraces"],
    "SA":  ["saudiracing", "racingpost", "attheraces"],
    "QAT": ["qrec", "racingpost", "attheraces"],
    "QA":  ["qrec", "racingpost", "attheraces"],
    "BHR": ["bahrainturfclub", "racingpost", "attheraces"],
    "BH":  ["bahrainturfclub", "racingpost", "attheraces"],
    "IND": ["indiarace", "bangaloreraces", "racingpulse", "rwitc", "racingpost"],
    "IN":  ["indiarace", "bangaloreraces", "racingpulse", "rwitc", "racingpost"],
    "ESP": ["jockeyclubspain", "racingpost", "attheraces"],
    "CZE": ["dostihyjc", "racingpost", "attheraces"],
    "OMN": ["rhrc", "racingpost", "attheraces"],
    # Default fallback (no country or unknown)
    "DEFAULT": ["racingpost", "attheraces", "britishhorseracing", "equibase"],
}

# ─────────────────────────────────────────────
# SCRAPER REGISTRY
# Key = scraper key, Value = dict with url and class name
# ─────────────────────────────────────────────
SCRAPER_REGISTRY: dict[str, dict] = {
    "racingpost":        {"url": "https://www.racingpost.com",              "module": "racingpost_scraper",     "class": "RacingPostScraper"},
    "attheraces":        {"url": "https://www.attheraces.com",              "module": "attheraces_scraper",     "class": "AtTheRacesScraper"},
    "britishhorseracing":{"url": "https://www.britishhorseracing.com",      "module": "britishhorseracing_scraper","class": "BritishHorseRacingScraper"},
    "hri":               {"url": "https://www.hri-ras.ie",                  "module": "hri_scraper",            "class": "HRIScraper"},
    "francegalop":       {"url": "https://www.france-galop.com",            "module": "francegalop_scraper",    "class": "FranceGalopScraper"},
    "deutschergalopp":   {"url": "https://www.deutscher-galopp.de",        "module": "deutschergalopp_scraper","class": "DeutscherGaloppScraper"},
    "emiratesracing":    {"url": "https://emiratesracing.com",              "module": "emiratesracing_scraper", "class": "EmiratesRacingScraper"},
    "qrec":              {"url": "https://qrec.gov.qa",                     "module": "qrec_scraper",           "class": "QRECScraper"},
    "bahrainturfclub":   {"url": "https://bahrainturfclub.com",             "module": "bahrain_scraper",        "class": "BahrainScraper"},
    "rhrc":              {"url": "http://www.rhrc.om",                      "module": "rhrc_scraper",           "class": "RHRCScraper"},
    "jockeyclubspain":   {"url": "https://jockey-club.es",                  "module": "spain_scraper",          "class": "SpainScraper"},
    "dostihyjc":         {"url": "http://www.dostihyjc.cz",                 "module": "czech_scraper",          "class": "CzechScraper"},
    "equibase":          {"url": "https://www.equibase.com",                "module": "equibase_scraper",       "class": "EquibaseScraper"},
    "racingaustralia":   {"url": "https://www.racingaustralia.horse",       "module": "racingaustralia_scraper","class": "RacingAustraliaScraper"},
    "racingvictoria":    {"url": "https://www.racingvictoria.com.au",       "module": "racingvictoria_scraper", "class": "RacingVictoriaScraper"},
    "jra":               {"url": "https://www.jra.go.jp",                   "module": "jra_scraper",            "class": "JRAScraper"},
    "netkeiba":          {"url": "https://en.netkeiba.com",                 "module": "netkeiba_scraper",       "class": "NetkeibaScraper"},
    "japanracing":       {"url": "https://japanracing.jp/en",               "module": "japanracing_scraper",    "class": "JapanRacingScraper"},
    "hkjc":              {"url": "https://www.hkjc.com",                    "module": "hkjc_scraper",           "class": "HKJCScraper"},
    "saudiracing":       {"url": "https://www.saudiracing.com",             "module": "saudiracing_scraper",    "class": "SaudiRacingScraper"},
    "indiarace":         {"url": "https://www.indiarace.com",               "module": "indiarace_scraper",      "class": "IndiaRaceScraper"},
    "bangaloreraces":    {"url": "https://www.bangaloreraces.com",          "module": "bangaloreraces_scraper", "class": "BangaloreRacesScraper"},
    "racingpulse":       {"url": "https://www.racingpulse.in",              "module": "racingpulse_scraper",    "class": "RacingPulseScraper"},
    "rwitc":             {"url": "https://www.rwitc.com",                   "module": "rwitc_scraper",          "class": "RWITCScraper"},
}

# ─────────────────────────────────────────────
# RACE TRACK / CENTRE SHORT CODE MAPPING
# Format: "Full Name / Alias" → "Code"
# ─────────────────────────────────────────────
TRACK_CODE_MAP: dict[str, str] = {
    # Saudi Arabia
    "riyadh": "R",
    "king abdulaziz": "K",
    "jockey club saudi arabia": "K",
    "king abdulaziz racecourse": "K",
    # UAE
    "meydan": "M",
    "abu dhabi": "AD",
    "jebel ali": "JA",
    # Hong Kong
    "sha tin": "ST",
    "happy valley": "HV",
    # UK
    "ascot": "A",
    "cheltenham": "CH",
    "epsom": "EP",
    "goodwood": "G",
    "newmarket": "NM",
    "newbury": "NB",
    "york": "Y",
    "sandown": "SAN",
    "kempton": "K",
    "lingfield": "LF",
    "doncaster": "DO",
    "haydock": "HY",
    "chester": "CS",
    "leicester": "LE",
    "nottingham": "NT",
    "windsor": "WI",
    "wolverhampton": "WO",
    "thirsk": "TH",
    "carlisle": "CA",
    "catterick": "CT",
    "hamilton": "HA",
    "musselburgh": "MU",
    "perth": "PE",
    "ayr": "AY",
    "bath": "BA",
    "beverley": "BE",
    "brighton": "BR",
    "chepstow": "CP",
    "exeter": "EX",
    "ffos las": "FF",
    "folkestone": "FO",
    "hereford": "HE",
    "huntingdon": "HU",
    "kempton park": "KP",
    "market rasen": "MR",
    "plumpton": "PL",
    "redcar": "RE",
    "ripon": "RI",
    "salisbury": "SA",
    "southwell": "SO",
    "stratford": "ST",
    "taunton": "TA",
    "towcester": "TO",
    "uttoxeter": "UT",
    "warwick": "WA",
    "wincanton": "WC",
    # Ireland
    "curragh": "CU",
    "leopardstown": "LP",
    "galway": "GL",
    "cork": "CO",
    "killarney": "KL",
    "tipperary": "TI",
    "limerick": "LI",
    "naas": "NA",
    "navan": "NV",
    "dundalk": "DU",
    "ballinrobe": "BL",
    "bellewstown": "BW",
    "clonmel": "CM",
    "downpatrick": "DP",
    "fairyhouse": "FH",
    "gowran park": "GP",
    "kilbeggan": "KB",
    "laytown": "LT",
    "listowel": "LW",
    "punchestown": "PU",
    "roscommon": "RO",
    "sligo": "SL",
    "thurles": "TH",
    "tralee": "TR",
    "tramore": "TM",
    "wexford": "WX",
    # France
    "longchamp": "LO",
    "chantilly": "CN",
    "deauville": "DV",
    "saint-cloud": "SC",
    "maisons-laffitte": "ML",
    "vincennes": "VI",
    "lyon": "LY",
    "bordeaux": "BO",
    "marseille": "MA",
    "toulouse": "TL",
    # Japan
    "tokyo": "TK",
    "nakayama": "NK",
    "kyoto": "KY",
    "hanshin": "HS",
    "sapporo": "SP",
    "hakodate": "HK",
    "fukushima": "FK",
    "niigata": "NG",
    "chukyo": "CK",
    "kokura": "KO",
    # Australia
    "flemington": "FL",
    "caulfield": "CF",
    "moonee valley": "MV",
    "sandown": "SN",
    "randwick": "RW",
    "rosehill": "RH",
    "warwick farm": "WF",
    "eagle farm": "EF",
    "doomben": "DB",
    "morphettville": "MO",
    "victoria park": "VP",
    # USA
    "churchill downs": "CD",
    "belmont park": "BP",
    "saratoga": "SR",
    "santa anita": "SA",
    "del mar": "DM",
    "gulfstream park": "GP",
    "aqueduct": "AQ",
    "keeneland": "KE",
    "pimlico": "PI",
    "oaklawn park": "OA",
    # Germany
    "cologne": "CO",
    "hamburg": "HB",
    "munich": "MU",
    "frankfurt": "FR",
    "dusseldorf": "DU",
    "berlin": "BE",
    # India
    "mahalaxmi": "MH",
    "bangalore": "BG",
    "hyderabad": "HY",
    "mysore": "MY",
    "pune": "PU",
    "delhi": "DE",
    "kolkata": "KO",
    "chennai": "CH",
    # Qatar
    "doha": "DO",
    "al rayyan": "AR",
    # Bahrain
    "rashid equestrian": "RE",
    "bahrain turf club": "BT",
    # Oman
    "muscat": "MC",
}

# ─────────────────────────────────────────────
# SURFACE TYPE MAPPING
# ─────────────────────────────────────────────
SURFACE_MAP: dict[str, str] = {
    "turf": "T",
    "grass": "T",
    "dirt": "D",
    "synthetic": "AW",
    "all weather": "AW",
    "all-weather": "AW",
    "polytrack": "AW",
    "tapeta": "AW",
    "fibresand": "AW",
    "good": "T",         # surface condition sometimes used as surface
    "firm": "T",
    "soft": "T",
    "heavy": "T",
    "yielding": "T",
}

# ─────────────────────────────────────────────
# EQUIPMENT / GEAR SHORT CODE MAPPING
# ─────────────────────────────────────────────
EQUIPMENT_CODE_MAP: dict[str, str] = {
    "blinkers": "B",
    "blinkered": "B",
    "tongue strap": "TS",
    "tongue tie": "TT",
    "cheekpieces": "CP",
    "hood": "H",
    "visor": "V",
    "pacifiers": "P",
    "ear muffs": "EM",
    "nasal strip": "NS",
    "sheepskin cheekpieces": "SCP",
    "sheepskin noseband": "SN",
    "market rasen hood": "MH",
    "shadow roll": "SR",
    "net hood": "NH",
    "crossed noseband": "CN",
    "first time blinkers": "B1",
    "australian noseband": "AN",
    "running martingale": "RM",
    "figure 8 noseband": "F8",
    "bandages": "BN",
    "eyehood": "EH",
    "off side blinker": "OSB",
    "near side blinker": "NSB",
    "no equipment": "",
    "none": "",
}

# ─────────────────────────────────────────────
# PLACING TEXT → NUMBER MAPPING
# ─────────────────────────────────────────────
PLACING_TEXT_MAP: dict[str, str] = {
    "1st": "1", "2nd": "2", "3rd": "3", "4th": "4", "5th": "5",
    "6th": "6", "7th": "7", "8th": "8", "9th": "9", "10th": "10",
    "first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5",
    "won": "1", "w": "1",
    "fell": "F", "f": "F",
    "pulled up": "PU", "pu": "PU",
    "unseated": "UR", "ur": "UR",
    "refused": "RF", "ref": "RF",
    "brought down": "BD", "bd": "BD",
    "carried out": "CO", "co": "CO",
    "slipped up": "SU", "su": "SU",
    "disqualified": "DQ", "dq": "DQ",
    "void": "V",
    "dns": "DNS",
    "dnf": "DNF",
    "scratched": "SCR", "scr": "SCR",
    "non-runner": "NR", "nr": "NR",
}

# ─────────────────────────────────────────────
# DATE FORMAT
# ─────────────────────────────────────────────
DATE_FORMAT = "%d-%m-%Y"

# ─────────────────────────────────────────────
# EXCEL OUTPUT COLUMN ORDER
# Exact headers as required
# ─────────────────────────────────────────────
EXCEL_COLUMNS = [
    "Horse Name",
    "Placing",
    "WeightAllotted",
    "WeightCarried",
    "Len",
    "JockeyName",
    "Pre_Rating_Official",
    "Post_Rating_Official",
    "Turf Rating",
    "PF",
    "Handicapper Comments",
    "RaceDate",
    "Meeting",
    "RaceNo",
    "RaceTrack",
    "RaceName",
    "RaceValue",
    "Group",
    "Surface",
    "AgeCond",
    "OtherCond",
    "Distance",
    "Starters",
    "Time",
    "StewardsComments",
    "H No",
    "D No",
    "Btn/Btn by",
    "Age",
    "Sex",
    "Position",
    "Jockey",
    "Equipment",
    "H[D]",
    "C(T)",
    "Wt",
    "Placing2",
    "HC",
    "SC",
    "Equip2",
    # Extra metadata
    "CountryCode",
    "RaceStatus",
    "SourceURL",
]

# ─────────────────────────────────────────────
# RACE STATUS VALUES
# ─────────────────────────────────────────────
RACE_STATUS_COMPLETED = "COMPLETED"
RACE_STATUS_UPCOMING = "UPCOMING"
RACE_STATUS_CANCELLED = "CANCELLED"
RACE_STATUS_ABANDONED = "ABANDONED"

# ─────────────────────────────────────────────
# GROUP/CLASS NORMALISATION
# ─────────────────────────────────────────────
GROUP_MAP: dict[str, str] = {
    "group 1": "G1", "group1": "G1", "gr.1": "G1", "gr1": "G1", "g1": "G1",
    "group 2": "G2", "group2": "G2", "gr.2": "G2", "gr2": "G2", "g2": "G2",
    "group 3": "G3", "group3": "G3", "gr.3": "G3", "gr3": "G3", "g3": "G3",
    "grade 1": "G1", "grade1": "G1",
    "grade 2": "G2", "grade2": "G2",
    "grade 3": "G3", "grade3": "G3",
    "listed": "L",
    "handicap": "H",
    "conditions": "C",
    "maiden": "M",
    "novice": "N",
    "allowance": "A",
    "claiming": "CL",
    "selling": "S",
    "stakes": "ST",
}
