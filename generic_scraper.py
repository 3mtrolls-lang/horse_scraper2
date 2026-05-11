"""
scrapers/generic_scraper.py
A generic scraper template used for country-specific websites that share
a common pattern: search form → horse profile → form table.

This module also serves as the implementation for multiple country scrapers
that follow the same basic pattern. Each country scraper file simply
instantiates GenericScraper with the appropriate configuration.
"""

import logging
import re
import sys
import os
from typing import Optional
from urllib.parse import quote_plus, urljoin

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper
from models import RaceRecord
from config import RACE_STATUS_COMPLETED, RACE_STATUS_UPCOMING
from scrapers.data_normaliser import (
    normalise_date, get_track_code, normalise_surface, normalise_placing,
    normalise_group, normalise_equipment, build_c_t, build_h_d, normalise_distance,
)
from weight_utils import normalise_weight
from horse_name_utils import fuzzy_match_name

logger = logging.getLogger("horse_scraper.generic")


class GenericScraper(BaseScraper):
    """
    Generic horse racing scraper.
    Configurable for different sites by overriding class attributes.
    """

    name = "Generic"
    base_url = ""

    # Subclasses can override these search patterns
    search_url_template: str = ""     # e.g. "{base}/search?q={query}"
    horse_link_pattern: str = r"/horse|/profile|/form"
    table_class_pattern: str = r"form|result|race|history"

    def search_horse(self, horse_name: str, country_code: str = "") -> Optional[str]:
        if not self.search_url_template:
            logger.debug("%s: no search URL configured", self.name)
            return None

        url = self.search_url_template.format(
            base=self.base_url,
            query=quote_plus(horse_name),
            name=horse_name.replace(" ", "+"),
        )
        logger.info("%s: searching '%s' at %s", self.name, horse_name, url)

        html = self.fetch(url)
        if not html:
            html = self.fetch_playwright(url)
        if not html:
            return None

        return self._extract_best_link(html, horse_name)

    def _extract_best_link(self, html: str, horse_name: str) -> Optional[str]:
        """Find the best-matching horse profile link in the HTML."""
        soup = self.parse_html(html)
        if not soup:
            return None

        links = soup.find_all("a", href=re.compile(self.horse_link_pattern, re.I))
        candidates = {}
        for link in links:
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and href and len(text) > 2:
                full_url = urljoin(self.base_url, href)
                candidates[text] = full_url

        if not candidates:
            return None

        best = fuzzy_match_name(horse_name, list(candidates.keys()))
        return candidates.get(best) if best else None

    def fetch_latest_run(self, horse_name: str, country_code: str = "") -> Optional[RaceRecord]:
        profile_url = self.search_horse(horse_name, country_code)
        if not profile_url:
            return None

        html = self.fetch(profile_url)
        if not html:
            html = self.fetch_playwright(profile_url)
        if not html:
            return None

        records = self._parse_form_table(html, horse_name, country_code, profile_url, limit=1)
        return records[0] if records else None

    def fetch_history(self, horse_name: str, country_code: str = "") -> list[RaceRecord]:
        profile_url = self.search_horse(horse_name, country_code)
        if not profile_url:
            return []

        html = self.fetch(profile_url)
        if not html:
            html = self.fetch_playwright(profile_url)
        if not html:
            return []

        return self._parse_form_table(html, horse_name, country_code, profile_url)

    def _parse_form_table(
        self,
        html: str,
        horse_name: str,
        country_code: str,
        source_url: str = "",
        limit: Optional[int] = None,
    ) -> list[RaceRecord]:
        """Parse any form table following common patterns."""
        soup = self.parse_html(html)
        if not soup:
            return []

        table = soup.find("table", class_=re.compile(self.table_class_pattern, re.I))
        if not table:
            # Try any table on the page
            tables = soup.find_all("table")
            table = tables[0] if tables else None
        if not table:
            return []

        records = []
        rows = table.find_all("tr")[1:]   # Skip header

        for row in rows:
            if limit and len(records) >= limit:
                break
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue

            def ct(i):
                return cells[i].get_text(separator=" ", strip=True) if i < len(cells) else ""

            raw_date   = ct(0)
            raw_course = ct(1)
            raw_pos    = ct(2)
            raw_dist   = ct(3) if len(cells) > 3 else ""
            raw_going  = ct(4) if len(cells) > 4 else ""
            raw_wt     = ct(5) if len(cells) > 5 else ""
            raw_jockey = ct(6) if len(cells) > 6 else ""
            raw_class  = ct(7) if len(cells) > 7 else ""
            raw_btn    = ct(8) if len(cells) > 8 else ""

            if not raw_date:
                continue

            placing_text, placing_num = normalise_placing(raw_pos)
            surface = normalise_surface(raw_going)
            track_code = get_track_code(raw_course)
            weight_kg = normalise_weight(raw_wt)

            rec = RaceRecord(
                horse_name      = horse_name,
                country_code    = country_code,
                race_date       = normalise_date(raw_date),
                meeting         = track_code,
                race_track      = track_code,
                surface         = surface,
                distance        = normalise_distance(raw_dist),
                group           = normalise_group(raw_class),
                placing         = placing_text,
                placing2        = placing_num,
                position        = placing_num,
                jockey_name     = raw_jockey,
                jockey          = raw_jockey,
                weight_allotted = weight_kg,
                weight_carried  = weight_kg,
                wt              = weight_kg,
                btn_by          = raw_btn,
                len             = raw_btn,
                c_t             = build_c_t(raw_course, surface),
                race_status     = RACE_STATUS_COMPLETED,
                source_url      = source_url or self.base_url,
                scraper_name    = self.name,
            )
            records.append(rec)

        return records


# ─────────────────────────────────────────────────────────────────────────────
# Country-specific scraper subclasses
# Each overrides name, base_url, and search_url_template.
# ─────────────────────────────────────────────────────────────────────────────

class BritishHorseRacingScraper(GenericScraper):
    name = "BritishHorseRacing"
    base_url = "https://www.britishhorseracing.com"
    search_url_template = "{base}/racing/horses/?search={query}"
    horse_link_pattern = r"/horses/|/racing/horse"


class HRIScraper(GenericScraper):
    name = "HRI"
    base_url = "https://www.hri-ras.ie"
    search_url_template = "{base}/full-flat-ratings?search={query}"
    horse_link_pattern = r"/horse|/rating"


class FranceGalopScraper(GenericScraper):
    name = "FranceGalop"
    base_url = "https://www.france-galop.com"
    search_url_template = "{base}/en/horses-and-people/ratings?search={query}"
    horse_link_pattern = r"/en/horse|/cheval"


class DeutscherGaloppScraper(GenericScraper):
    name = "DeutscherGalopp"
    base_url = "https://www.deutscher-galopp.de"
    search_url_template = "{base}/gr/pferd/suche.php?search={query}"
    horse_link_pattern = r"/pferd/|/horse/"


class EmiratesRacingScraper(GenericScraper):
    name = "EmiratesRacing"
    base_url = "https://emiratesracing.com"
    search_url_template = "{base}/horses/thoroughbred?search={query}"
    horse_link_pattern = r"/horses/|/horse/"


class QRECScraper(GenericScraper):
    name = "QREC"
    base_url = "https://qrec.gov.qa"
    search_url_template = "{base}/racing/handicap-ratings/?search={query}"
    horse_link_pattern = r"/horse|/racing"


class BahrainScraper(GenericScraper):
    name = "BahrainTurfClub"
    base_url = "https://bahrainturfclub.com"
    search_url_template = "{base}/horses/local?search={query}"
    horse_link_pattern = r"/horses/"


class RHRCScraper(GenericScraper):
    name = "RHRC"
    base_url = "http://www.rhrc.om"
    search_url_template = "{base}/Calendar.aspx?T=H&PID=4&search={query}"
    horse_link_pattern = r"/horse|/Calendar"


class SpainScraper(GenericScraper):
    name = "JockeyClubSpain"
    base_url = "https://jockey-club.es"
    search_url_template = "{base}/valores-oficiales-2/?search={query}"
    horse_link_pattern = r"/horse|/caballo"


class CzechScraper(GenericScraper):
    name = "DostihyJC"
    base_url = "http://www.dostihyjc.cz"
    search_url_template = "{base}/index.php?page=7&search={query}"
    horse_link_pattern = r"/horse|/kun"


class EquibaseScraper(GenericScraper):
    name = "Equibase"
    base_url = "https://www.equibase.com"
    search_url_template = "{base}/static/entry/search.cfm?search={query}"
    horse_link_pattern = r"/Horse/USA|/horse/"


class RacingAustraliaScraper(GenericScraper):
    name = "RacingAustralia"
    base_url = "https://www.racingaustralia.horse"
    search_url_template = "{base}/search?q={query}"
    horse_link_pattern = r"/horse|/form"


class RacingVictoriaScraper(GenericScraper):
    name = "RacingVictoria"
    base_url = "https://www.racingvictoria.com.au"
    search_url_template = "{base}/horses?search={query}"
    horse_link_pattern = r"/horse|/form"


class JRAScraper(GenericScraper):
    name = "JRA"
    base_url = "https://www.jra.go.jp"
    search_url_template = "{base}/datafile/search/?search={query}"
    horse_link_pattern = r"/horse|/datafile"


class NetkeibaScraper(GenericScraper):
    name = "Netkeiba"
    base_url = "https://en.netkeiba.com"
    search_url_template = "{base}/search/horse/?query={query}"
    horse_link_pattern = r"/horse/|/db/horse/"


class JapanRacingScraper(GenericScraper):
    name = "JapanRacing"
    base_url = "https://japanracing.jp"
    search_url_template = "{base}/en/?search={query}"
    horse_link_pattern = r"/horse|/en/"


class HKJCScraper(GenericScraper):
    name = "HKJC"
    base_url = "https://www.hkjc.com"
    search_url_template = "{base}/racing/en-us/horse-profile/search?horse={query}"
    horse_link_pattern = r"/racing/en-us/horse"


class SaudiRacingScraper(GenericScraper):
    name = "SaudiRacing"
    base_url = "https://www.saudiracing.com"
    search_url_template = "{base}/horses?search={query}"
    horse_link_pattern = r"/horses/|/horse/"


class IndiaRaceScraper(GenericScraper):
    name = "IndiaRace"
    base_url = "https://www.indiarace.com"
    search_url_template = "{base}/horse_profile.asp?HorseName={query}"
    horse_link_pattern = r"/horse_profile|/form"


class BangaloreRacesScraper(GenericScraper):
    name = "BangaloreRaces"
    base_url = "https://www.bangaloreraces.com"
    search_url_template = "{base}/horses?search={query}"
    horse_link_pattern = r"/horse|/result"


class RacingPulseScraper(GenericScraper):
    name = "RacingPulse"
    base_url = "https://www.racingpulse.in"
    search_url_template = "{base}/search?q={query}"
    horse_link_pattern = r"/horse|/form"


class RWITCScraper(GenericScraper):
    name = "RWITC"
    base_url = "https://www.rwitc.com"
    search_url_template = "{base}/horses?search={query}"
    horse_link_pattern = r"/horse|/form"
