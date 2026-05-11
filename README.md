# 🏇 Horse Racing Data Scraper

A production-grade Python application to scrape race results and history for international horses, with intelligent country-aware routing and Excel export.

---

## 📁 Project Structure

```
horse_scraper/
├── main.py                    ← Entry point (run this)
├── config.py                  ← All settings, mappings, constants
├── models.py                  ← RaceRecord + HorseInput dataclasses
├── router.py                  ← Country-aware scraper routing
├── logging_utils.py           ← Rich + file logging setup
├── excel_utils.py             ← Excel export with formatting
├── horse_name_utils.py        ← Name parsing + fuzzy matching
├── weight_utils.py            ← Weight conversion (stones/lbs → kg)
├── base_scraper.py            ← Abstract base class for scrapers
├── requirements.txt           ← Python dependencies
├── scrapers/
│   ├── __init__.py
│   ├── data_normaliser.py     ← Shared normalisation helpers
│   ├── racingpost_scraper.py  ← Racing Post (primary)
│   ├── attheraces_scraper.py  ← At The Races (secondary)
│   ├── generic_scraper.py     ← Generic base + all country scrapers
│   ├── jra_scraper.py         ← JRA Japan
│   ├── hkjc_scraper.py        ← Hong Kong Jockey Club
│   ├── equibase_scraper.py    ← USA Equibase
│   ├── saudiracing_scraper.py ← Saudi Racing
│   └── ... (22 scrapers total)
├── output/                    ← Excel output files (auto-created)
├── logs/                      ← Log files (auto-created)
├── cache/                     ← HTTP response cache (auto-created)
└── samples/
    └── create_sample_input.py ← Generate a test input Excel file
```

---

## ⚡ Quick Start

### Local PC

```bash
# 1. Clone / unzip the project
cd horse_scraper

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Playwright browser
python -m playwright install chromium

# 4. Run
python main.py
```

### Google Colab

```python
# Cell 1: Upload the project zip and unzip
# (or clone from GitHub)

# Cell 2: Install dependencies
!pip install -r horse_scraper/requirements.txt -q
!python -m playwright install chromium

# Cell 3: Run interactively
%cd horse_scraper
from main import run_in_colab

# Option A: Manual list
run_in_colab(["Equinox (JPN)", "Romantic Warrior (IRE)", "Frankel (GB)"])

# Option B: Excel file
run_in_colab(excel_path="samples/sample_horses.xlsx")
```

---

## 🐴 Input Formats

### Manual Entry
```
Equinox (JPN)
Romantic Warrior (IRE)
Frankel (GB)
Flightline (USA)
Golden Sixty (HK)
Winx (AUS)
```

Supported country codes: `JPN`, `GB`, `IRE`, `USA`, `HK`, `FR`, `AUS`, `GER`, `UAE`, `SAU`, `QAT`, `BHR`, `IND`, `ESP`, `CZE`, `OMN`, and more.

### Excel Import
- Horse names in **Column A**
- Format: `Forever Young (JPN)` or just `Forever Young`
- Country code in brackets is optional but recommended for routing

---

## 📊 Output Files

Two Excel files are saved to the `output/` directory:

| File | Contents |
|------|----------|
| `latest_run_TIMESTAMP.xlsx` | Most recent completed race OR nearest upcoming entry per horse |
| `history_TIMESTAMP.xlsx` | Full race history for all horses |

Both files contain:
- **Main data sheet** with all 42 columns
- **Upcoming Entries sheet** (in latest_run file only)
- **Summary sheet** (in history file) with win stats
- **Reference sheet** — centre/track codes + equipment codes

### Excel Columns

| Column | Description |
|--------|-------------|
| Horse Name | Clean name (no country code) |
| Placing | "1st", "2nd", etc. |
| Placing2 | Numeric: "1", "2", etc. |
| WeightAllotted | kg |
| WeightCarried | kg (falls back to allotted) |
| JockeyName / Jockey | Full jockey name (both columns filled) |
| Equipment | Full names: "Blinkers; Tongue Strap" |
| Equip2 | Short codes: "B; TS" |
| HC / Handicapper Comments | Same field, both columns filled |
| SC / StewardsComments | Same field, both columns filled |
| H[D] | Horse No [Draw No]: "3[5]" |
| C(T) | Centre (Track type): "M(T)" |
| RaceStatus | COMPLETED or UPCOMING |

---

## 🌍 Scraper Priority

| Country Code | Primary Sources |
|---|---|
| JPN / JP | JRA → Netkeiba → Japan Racing → Racing Post |
| HK | HKJC → Racing Post |
| USA | Equibase → Racing Post |
| GB / UK | Racing Post → British Horse Racing → At The Races |
| IRE | Racing Post → HRI → At The Races |
| FR | Racing Post → France Galop |
| AUS | Racing Post → Racing Australia → Racing Victoria |
| UAE | Racing Post → Emirates Racing |
| SAU | Saudi Racing → Racing Post |
| QAT | QREC → Racing Post |
| BHR | Bahrain Turf Club → Racing Post |
| IND | India Race → Bangalore Races → Racing Pulse → RWITC |
| (none/unknown) | Racing Post → At The Races → British Horse Racing |

---

## ⚙️ Configuration (`config.py`)

All settings in one place:

```python
MAX_WORKERS = 4          # Concurrent threads
CACHE_TTL_HOURS = 24     # Response cache lifetime
FUZZY_MATCH_THRESHOLD = 80  # Horse name matching score
RANDOM_DELAY_MIN = 1.5   # Polite delay between requests (seconds)
RANDOM_DELAY_MAX = 4.0
MAX_RETRIES = 3
```

Add new track codes to `TRACK_CODE_MAP`, equipment to `EQUIPMENT_CODE_MAP`.

---

## 🔧 Adding a New Scraper

1. Add an entry to `SCRAPER_REGISTRY` in `config.py`
2. Add country routing to `COUNTRY_SCRAPER_PRIORITY`
3. Create `scrapers/mysite_scraper.py`:

```python
from scrapers.generic_scraper import GenericScraper

class MySiteScraper(GenericScraper):
    name = "MySite"
    base_url = "https://www.mysite.com"
    search_url_template = "{base}/search?q={query}"
    horse_link_pattern = r"/horse/"
```

---

## ⚠️ Important Notes

- **Anti-bot protection**: Some sites (Racing Post, HKJC) use Cloudflare. `cloudscraper` handles most cases; Playwright is the fallback for JS-heavy pages.
- **Rate limiting**: Random delays (1.5–4s) between requests are built in. Increase if you get blocked.
- **Caching**: Responses are cached for 24h in `cache/`. Use `--no-cache` to bypass.
- **Robots.txt**: Respect `robots.txt` where possible. This tool is for personal research use.

---

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: cloudscraper` | `pip install cloudscraper` |
| `ModuleNotFoundError: rapidfuzz` | `pip install rapidfuzz` |
| Site returns 403 | Increase delays in `config.py`, or the site requires login |
| Playwright not found | `pip install playwright && python -m playwright install chromium` |
| Empty results | Check logs in `logs/` — site may have changed structure |
| Weight not converting | Verify format — "9-2" (stones-pounds), "126" (lbs), "57.5kg" (kg) |
