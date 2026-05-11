"""
scrapers/attheraces_scraper.py
Scraper for At The Races (attheraces.com) — secondary international source.
"""

import logging
import re
import sys
import os
from typing import Optional
from urllib.parse import quote_plus

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper
from models import RaceRecord
from config import RACE_STATUS_COMPLETED, RACE_STATUS_UPCOMING
from scrapers.data_normaliser import (
    normalise_date, get_track_code, normalise_group, normalise_surface,
    normalise_placing, normalise_equipment, build_c_t, build_h_d,
    normalise_distance,
)
from weight_utils import normalise_weight
from horse_name_utils import fuzzy_match_name

logger = logging.getLogger("horse_scraper.attheraces")

_BASE = "https://www.attheraces.com"
_SEARCH_URL = _BASE + "/form/horse/{slug}"
_SEARCH_API = _BASE + "/api/horses/search?q={query}"


class AtTheRacesScraper(BaseScraper):
    """Scrapes At The Races for horse profiles and form."""

    name = "AtTheRaces"
    base_url = _BASE

    def search_horse(self, horse_name: str, country_code: str = "") -> Optional[str]:
        query = quote_plus(horse_name)
        api_url = _SEARCH_API.format(query=query)
        logger.info("%s: searching for '%s'", self.name, horse_name)

        html = self.fetch(api_url)
        if not html:
            return None

        return self._extract_profile_url(html, horse_name)

    def _extract_profile_url(self, html: str, horse_name: str) -> Optional[str]:
        # Try JSON first
        try:
            import json
            data = json.loads(html)
            items = data if isinstance(data, list) else data.get("horses", data.get("results", []))
            candidates = {}
            for item in items:
                name = item.get("name", item.get("horseName", ""))
                url = item.get("url", item.get("profileUrl", ""))
                if name and url:
                    full_url = _BASE + url if url.startswith("/") else url
                    candidates[name] = full_url
            if candidates:
                best = fuzzy_match_name(horse_name, list(candidates.keys()))
                if best:
                    return candidates[best]
        except Exception:
            pass

        # Fallback: parse HTML
        soup = self.parse_html(html)
        if not soup:
            return None

        links = soup.find_all("a", href=re.compile(r"/horse|/form", re.I))
        candidates = {}
        for link in links:
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and href:
                candidates[text] = _BASE + href if href.startswith("/") else href

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

        records = self._parse_form(html, horse_name, country_code, limit=1)
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

        return self._parse_form(html, horse_name, country_code)

    def _parse_form(
        self,
        html: str,
        horse_name: str,
        country_code: str,
        limit: Optional[int] = None,
    ) -> list[RaceRecord]:
        soup = self.parse_html(html)
        if not soup:
            return []

        records = []

        # ATR form tables have class "form-table" or similar
        table = soup.find("table", class_=re.compile(r"form|result|race", re.I))
        if not table:
            table = soup.find("div", class_=re.compile(r"formTable|form-guide", re.I))
        if not table:
            return []

        rows = table.find_all("tr")[1:]  # Skip header
        for row in rows:
            if limit and len(records) >= limit:
                break
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue

            def ct(i):
                return cells[i].get_text(separator=" ", strip=True) if i < len(cells) else ""

            raw_date   = ct(0)
            raw_course = ct(1)
            raw_dist   = ct(2)
            raw_going  = ct(3)
            raw_class  = ct(4)
            raw_pos    = ct(5)
            raw_jockey = ct(6)
            raw_wt     = ct(7)
            raw_btn    = ct(8)
            raw_or     = ct(9)

            if not raw_date:
                continue

            placing_text, placing_num = normalise_placing(raw_pos)
            surface = normalise_surface(raw_going)
            track_code = get_track_code(raw_course)
            weight_kg = normalise_weight(raw_wt)

            rec = RaceRecord(
                horse_name        = horse_name,
                country_code      = country_code,
                race_date         = normalise_date(raw_date),
                meeting           = track_code,
                race_track        = track_code,
                surface           = surface,
                distance          = normalise_distance(raw_dist),
                group             = normalise_group(raw_class),
                placing           = placing_text,
                placing2          = placing_num,
                position          = placing_num,
                jockey_name       = raw_jockey,
                jockey            = raw_jockey,
                weight_allotted   = weight_kg,
                weight_carried    = weight_kg,
                wt                = weight_kg,
                btn_by            = raw_btn,
                len               = raw_btn,
                pre_rating_official = raw_or,
                c_t               = build_c_t(raw_course, surface),
                race_status       = RACE_STATUS_COMPLETED,
                source_url        = profile_url if 'profile_url' in dir() else _BASE,
                scraper_name      = self.name,
            )
            records.append(rec)

        return records
