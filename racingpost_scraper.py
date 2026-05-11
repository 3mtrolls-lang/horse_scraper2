"""
scrapers/racingpost_scraper.py
Scraper for Racing Post (racingpost.com) — primary international source.

Racing Post is the main aggregator for UK, Irish, international racing.
The scraper uses their search endpoint then parses the horse profile page.

NOTE: Racing Post may block bots. Playwright fallback is used if needed.
"""

import logging
import re
import sys
import os
from typing import Optional
from urllib.parse import quote_plus

# Allow imports from parent directory
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
from horse_name_utils import fuzzy_match_name, normalise_name

logger = logging.getLogger("horse_scraper.racingpost")

_BASE = "https://www.racingpost.com"
_SEARCH_URL = _BASE + "/horses/index.sd#q={query}&pageType=1&page=1"
_HORSE_URL  = _BASE + "/horses/{horse_id}/form"


class RacingPostScraper(BaseScraper):
    """
    Scrapes Racing Post for horse profiles, race results, and history.
    """

    name = "RacingPost"
    base_url = _BASE

    # ──────────────────────────────────────────────────────────────
    # SEARCH
    # ──────────────────────────────────────────────────────────────
    def search_horse(self, horse_name: str, country_code: str = "") -> Optional[str]:
        """
        Search Racing Post for a horse by name.
        Returns the horse profile URL or None.
        """
        query = horse_name
        if country_code:
            query = f"{horse_name} {country_code}"

        search_url = f"{_BASE}/horses/index.sd#q={quote_plus(query)}&pageType=1"
        logger.info("%s: searching for '%s'", self.name, query)

        # Racing Post search uses JS — try direct URL pattern first
        # e.g. racingpost.com/horses/horse-name--12345/form
        profile_url = self._try_direct_url(horse_name)
        if profile_url:
            return profile_url

        # Try API search endpoint
        api_url = f"{_BASE}/api/horses/search?q={quote_plus(horse_name)}&page=1"
        html = self.fetch(api_url, use_cache=True)
        if not html:
            # Fallback: Playwright to render JS search
            html = self.fetch_playwright(search_url)

        if not html:
            logger.warning("%s: no search results for '%s'", self.name, horse_name)
            return None

        return self._extract_profile_url(html, horse_name)

    def _try_direct_url(self, horse_name: str) -> Optional[str]:
        """
        Try Racing Post's predictable URL pattern for horse profiles.
        Pattern: /horses/<slug>--<id>/form
        We can't know the ID without searching, but we can try the search
        via their open search page.
        """
        slug = re.sub(r"[^a-z0-9]+", "-", horse_name.lower()).strip("-")
        # Try a few likely IDs (not reliable without knowing the actual ID)
        # Rely on search instead — return None here
        return None

    def _extract_profile_url(self, html: str, horse_name: str) -> Optional[str]:
        """
        Extract the best-matching horse profile URL from search result HTML/JSON.
        """
        soup = self.parse_html(html)
        if not soup:
            return None

        # Racing Post search results — look for horse links
        links = soup.find_all("a", href=re.compile(r"/horses/\S+/form"))
        if not links:
            # Try JSON response
            try:
                import json
                data = json.loads(html)
                horses = data.get("horses", data.get("results", []))
                candidates = {
                    h.get("name", ""): _BASE + h.get("url", "")
                    for h in horses
                    if h.get("name")
                }
                best = fuzzy_match_name(horse_name, list(candidates.keys()))
                if best:
                    return candidates[best]
            except Exception:
                pass
            return None

        candidates = {}
        for link in links:
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if text and href:
                candidates[text] = _BASE + href if href.startswith("/") else href

        if not candidates:
            return None

        best = fuzzy_match_name(horse_name, list(candidates.keys()))
        if best:
            logger.info("%s: matched '%s' → '%s'", self.name, horse_name, best)
            return candidates[best]

        return None

    # ──────────────────────────────────────────────────────────────
    # LATEST RUN
    # ──────────────────────────────────────────────────────────────
    def fetch_latest_run(self, horse_name: str, country_code: str = "") -> Optional[RaceRecord]:
        """
        Fetch the most recent completed OR nearest upcoming race.
        """
        profile_url = self.search_horse(horse_name, country_code)
        if not profile_url:
            logger.warning("%s: horse profile not found for '%s'", self.name, horse_name)
            return None

        html = self.fetch(profile_url)
        if not html:
            html = self.fetch_playwright(profile_url)
        if not html:
            return None

        records = self._parse_form_table(html, horse_name, country_code, limit=1)

        # Also check upcoming entries
        upcoming = self._fetch_upcoming(profile_url, horse_name, country_code)

        if upcoming:
            # Return the nearest upcoming race if available
            logger.info("%s: upcoming entry found for '%s'", self.name, horse_name)
            return upcoming[0]  # Nearest first

        return records[0] if records else None

    # ──────────────────────────────────────────────────────────────
    # FULL HISTORY
    # ──────────────────────────────────────────────────────────────
    def fetch_history(self, horse_name: str, country_code: str = "") -> list[RaceRecord]:
        """
        Fetch all available race history.
        """
        profile_url = self.search_horse(horse_name, country_code)
        if not profile_url:
            return []

        all_records: list[RaceRecord] = []
        page = 1
        max_pages = 20   # Safety limit

        while page <= max_pages:
            page_url = profile_url if page == 1 else f"{profile_url}?page={page}"
            html = self.fetch(page_url)
            if not html:
                html = self.fetch_playwright(page_url)
            if not html:
                break

            records = self._parse_form_table(html, horse_name, country_code)
            if not records:
                break

            all_records.extend(records)
            logger.info(
                "%s: fetched page %d (%d records so far) for '%s'",
                self.name, page, len(all_records), horse_name
            )

            # Check if there's a next page
            soup = self.parse_html(html)
            if soup:
                next_link = soup.find("a", string=re.compile(r"next|›|»", re.I))
                if not next_link:
                    break
            else:
                break

            page += 1

        # Also append upcoming entries to history
        if profile_url:
            upcoming = self._fetch_upcoming(profile_url, horse_name, country_code)
            all_records = upcoming + all_records  # Upcoming first

        logger.info("%s: total %d records for '%s'", self.name, len(all_records), horse_name)
        return all_records

    # ──────────────────────────────────────────────────────────────
    # UPCOMING ENTRIES
    # ──────────────────────────────────────────────────────────────
    def _fetch_upcoming(
        self, profile_url: str, horse_name: str, country_code: str
    ) -> list[RaceRecord]:
        """
        Check the entries/declarations section of the horse profile.
        """
        entries_url = profile_url.replace("/form", "/entries")
        html = self.fetch(entries_url, use_cache=False)
        if not html:
            html = self.fetch_playwright(entries_url)
        if not html:
            return []

        return self._parse_upcoming_table(html, horse_name, country_code)

    # ──────────────────────────────────────────────────────────────
    # HTML PARSERS
    # ──────────────────────────────────────────────────────────────
    def _parse_form_table(
        self,
        html: str,
        horse_name: str,
        country_code: str,
        limit: Optional[int] = None,
    ) -> list[RaceRecord]:
        """
        Parse the Racing Post form guide table.
        Returns list of RaceRecord objects.
        """
        soup = self.parse_html(html)
        if not soup:
            return []

        records = []
        # Racing Post form rows have data attributes on <tr class="rp-table-row">
        # or similar — structure varies; we cover the main patterns.
        table = soup.find("table", class_=re.compile(r"form|race-result", re.I))
        if not table:
            # Try alternative selectors
            table = soup.find("div", class_=re.compile(r"formTable|horse-form", re.I))

        if not table:
            logger.debug("%s: no form table found in page for '%s'", self.name, horse_name)
            return []

        rows = table.find_all("tr", class_=re.compile(r"row|result", re.I))
        if not rows:
            rows = table.find_all("tr")[1:]   # Skip header row

        for row in rows:
            if limit and len(records) >= limit:
                break

            record = self._parse_row(row, horse_name, country_code)
            if record:
                records.append(record)

        return records

    def _parse_row(self, row, horse_name: str, country_code: str) -> Optional[RaceRecord]:
        """Parse a single form table row into a RaceRecord."""
        cells = row.find_all(["td", "th"])
        if len(cells) < 4:
            return None

        # Extract text from each cell (strip tags)
        def ct(idx: int) -> str:
            if idx < len(cells):
                return cells[idx].get_text(separator=" ", strip=True)
            return ""

        # ── Map typical Racing Post column order ──
        # Columns vary — use data-attr names where available
        data = {}
        for cell in cells:
            for attr in cell.attrs:
                if attr.startswith("data-"):
                    key = attr.replace("data-", "")
                    data[key] = cell.get_text(strip=True)

        # Fallback: positional extraction
        # Typical RP order: date, course, dist, going, class, pos, horse, draw, age, wt, jockey, trainer, sp, btn, time, OR, comment
        raw_date   = data.get("date", ct(0))
        raw_course = data.get("course", ct(1))
        raw_dist   = data.get("dist", ct(2))
        raw_going  = data.get("going", ct(3))
        raw_class  = data.get("class", ct(4))
        raw_pos    = data.get("pos", data.get("position", ct(5)))
        raw_draw   = data.get("draw", ct(7))
        raw_age    = data.get("age", ct(8))
        raw_wt     = data.get("wt", ct(9))
        raw_jockey = data.get("jockey", ct(10))
        raw_btn    = data.get("btn", ct(13))
        raw_time   = data.get("time", ct(14))
        raw_or     = data.get("or", ct(15))
        raw_comment= data.get("comment", ct(16) if len(cells) > 16 else "")
        raw_equip  = data.get("equipment", data.get("gear", ""))
        raw_rn     = data.get("rn", data.get("race-number", ""))
        raw_hn     = data.get("hn", data.get("horse-number", ""))
        raw_starters = data.get("starters", data.get("runners", ""))
        raw_prize  = data.get("prize", data.get("race-value", ""))

        placing_text, placing_num = normalise_placing(raw_pos)
        equip_full, equip_code = normalise_equipment(raw_equip)
        weight_kg = normalise_weight(raw_wt)
        track_code = get_track_code(raw_course)
        surface = normalise_surface(raw_going)
        c_t_val = build_c_t(raw_course, surface)
        h_d_val = build_h_d(raw_hn, raw_draw)

        rec = RaceRecord(
            horse_name        = horse_name,
            country_code      = country_code,
            race_date         = normalise_date(raw_date),
            meeting           = track_code,
            race_no           = raw_rn,
            race_track        = track_code,
            race_name         = data.get("race-name", ""),
            race_value        = raw_prize,
            group             = normalise_group(raw_class),
            surface           = surface,
            distance          = normalise_distance(raw_dist),
            starters          = raw_starters,
            placing           = placing_text,
            placing2          = placing_num,
            position          = placing_num,
            h_no              = raw_hn,
            d_no              = raw_draw,
            h_d               = h_d_val,
            weight_allotted   = weight_kg,
            weight_carried    = weight_kg,
            wt                = weight_kg,
            jockey_name       = raw_jockey,
            jockey            = raw_jockey,
            btn_by            = raw_btn,
            len               = raw_btn,
            pre_rating_official = raw_or,
            time              = raw_time,
            equipment         = equip_full,
            equip2            = equip_code,
            c_t               = c_t_val,
            age               = raw_age,
            race_status       = RACE_STATUS_COMPLETED,
            source_url        = self.base_url,
            scraper_name      = self.name,
        )
        # Copy HC / SC
        rec.hc = data.get("hc", data.get("handicapper-comment", ""))
        rec.sc = data.get("sc", data.get("stewards-comment", ""))
        rec.handicapper_comments = rec.hc
        rec.stewards_comments = rec.sc

        return rec

    def _parse_upcoming_table(
        self, html: str, horse_name: str, country_code: str
    ) -> list[RaceRecord]:
        """Parse the entries/declarations page for upcoming races."""
        soup = self.parse_html(html)
        if not soup:
            return []

        records = []
        # Look for entry/declaration tables
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")[1:]
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 3:
                    continue

                def ct(i):
                    return cells[i].get_text(strip=True) if i < len(cells) else ""

                raw_date   = ct(0)
                raw_course = ct(1)
                raw_race   = ct(2)
                raw_dist   = ct(3)
                raw_going  = ct(4)
                raw_class  = ct(5)
                raw_status = ct(6)    # entered / declared / scratched
                raw_jockey = ct(7)
                raw_wt     = ct(8)
                raw_prize  = ct(9)

                if not raw_date:
                    continue

                track_code = get_track_code(raw_course)
                surface = normalise_surface(raw_going)
                weight_kg = normalise_weight(raw_wt)

                rec = RaceRecord(
                    horse_name        = horse_name,
                    country_code      = country_code,
                    race_date         = normalise_date(raw_date),
                    meeting           = track_code,
                    race_track        = track_code,
                    race_name         = raw_race,
                    race_value        = raw_prize,
                    group             = normalise_group(raw_class),
                    surface           = surface,
                    distance          = normalise_distance(raw_dist),
                    jockey_name       = raw_jockey,
                    jockey            = raw_jockey,
                    weight_allotted   = weight_kg,
                    wt                = weight_kg,
                    c_t               = build_c_t(raw_course, surface),
                    race_status       = RACE_STATUS_UPCOMING,
                    source_url        = self.base_url + "/entries",
                    scraper_name      = self.name,
                )
                # Status field
                rec.other_cond = raw_status
                records.append(rec)

        # Sort by date ascending (nearest first)
        records.sort(key=lambda r: r.race_date)
        return records
