"""
base_scraper.py - Abstract base class that all scrapers must inherit from.

Provides:
  - Session management with rotating user agents
  - cloudscraper / requests fallback
  - Retry logic via tenacity
  - Random delay between requests
  - Caching (file-based JSON cache)
  - Playwright fallback for JS-heavy pages
"""

import abc
import hashlib
import json
import logging
import os
import random
import time
from typing import Optional

import requests

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_random_exponential,
        retry_if_exception_type,
    )
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False

from config import (
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_WAIT_MIN,
    RETRY_WAIT_MAX,
    RANDOM_DELAY_MIN,
    RANDOM_DELAY_MAX,
    USER_AGENTS,
    CACHE_DIR,
    CACHE_TTL_HOURS,
)
from models import RaceRecord

logger = logging.getLogger("horse_scraper.base_scraper")


class BaseScraper(abc.ABC):
    """
    Abstract base class for all horse racing scrapers.
    """

    #: Override in subclass — display name for logging
    name: str = "BaseScraper"
    #: Override in subclass — base URL of the target site
    base_url: str = ""

    def __init__(self):
        self._session: Optional[requests.Session] = None
        self._init_session()

    # ─────────────────────────────────────────────────────────────
    # SESSION MANAGEMENT
    # ─────────────────────────────────────────────────────────────
    def _init_session(self) -> None:
        """Initialise a requests / cloudscraper session."""
        if HAS_CLOUDSCRAPER:
            try:
                self._session = cloudscraper.create_scraper(
                    browser={"browser": "chrome", "platform": "windows", "mobile": False}
                )
                logger.debug("%s: using cloudscraper session", self.name)
                return
            except Exception as exc:
                logger.debug("%s: cloudscraper init failed (%s), falling back to requests", self.name, exc)

        self._session = requests.Session()
        logger.debug("%s: using requests session", self.name)

    def _rotate_headers(self) -> dict:
        """Return headers with a randomly chosen User-Agent."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "no-cache",
        }

    # ─────────────────────────────────────────────────────────────
    # CACHING
    # ─────────────────────────────────────────────────────────────
    def _cache_path(self, url: str) -> str:
        key = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(CACHE_DIR, f"{self.name}_{key}.json")

    def _cache_get(self, url: str) -> Optional[str]:
        """Return cached HTML if fresh, else None."""
        path = self._cache_path(url)
        if not os.path.exists(path):
            return None
        mtime = os.path.getmtime(path)
        age_hours = (time.time() - mtime) / 3600
        if age_hours > CACHE_TTL_HOURS:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("html")

    def _cache_set(self, url: str, html: str) -> None:
        """Store HTML in cache."""
        path = self._cache_path(url)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"html": html, "url": url}, f)

    # ─────────────────────────────────────────────────────────────
    # HTTP FETCH (with retry + cache)
    # ─────────────────────────────────────────────────────────────
    def fetch(self, url: str, use_cache: bool = True, **kwargs) -> Optional[str]:
        """
        Fetch a URL and return the HTML string.
        Returns None on failure.

        Uses cache by default. Adds random delay, rotates headers, retries.
        """
        if use_cache:
            cached = self._cache_get(url)
            if cached:
                logger.debug("%s: cache hit for %s", self.name, url)
                return cached

        # Random polite delay
        time.sleep(random.uniform(RANDOM_DELAY_MIN, RANDOM_DELAY_MAX))

        headers = self._rotate_headers()
        headers.update(kwargs.pop("headers", {}))

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self._session.get(
                    url,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    **kwargs,
                )
                resp.raise_for_status()
                html = resp.text

                if use_cache:
                    self._cache_set(url, html)

                return html

            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "?"
                logger.warning(
                    "%s: HTTP %s on attempt %d/%d for %s",
                    self.name, status, attempt, MAX_RETRIES, url
                )
                if status in (403, 429):
                    # Rate limited — back off longer
                    time.sleep(random.uniform(RETRY_WAIT_MIN * 3, RETRY_WAIT_MAX * 3))
                elif status in (404, 410):
                    logger.info("%s: page not found: %s", self.name, url)
                    return None
                else:
                    time.sleep(random.uniform(RETRY_WAIT_MIN, RETRY_WAIT_MAX))

            except requests.exceptions.RequestException as exc:
                logger.warning(
                    "%s: request error on attempt %d/%d: %s",
                    self.name, attempt, MAX_RETRIES, exc
                )
                time.sleep(random.uniform(RETRY_WAIT_MIN, RETRY_WAIT_MAX))

        logger.error("%s: all %d attempts failed for %s", self.name, MAX_RETRIES, url)
        return None

    def fetch_playwright(self, url: str) -> Optional[str]:
        """
        Playwright fallback for JS-heavy pages.
        Returns rendered HTML string or None.
        """
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            logger.debug("%s: playwright not installed, skipping JS render", self.name)
            return None

        logger.info("%s: using Playwright to render %s", self.name, url)
        html = None
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    locale="en-US",
                )
                page = context.new_page()
                page.goto(url, wait_until="networkidle", timeout=30_000)
                # Extra wait for dynamic content
                time.sleep(2)
                html = page.content()
                browser.close()
        except Exception as exc:
            logger.warning("%s: Playwright error on %s: %s", self.name, url, exc)

        return html

    # ─────────────────────────────────────────────────────────────
    # BeautifulSoup helper
    # ─────────────────────────────────────────────────────────────
    def parse_html(self, html: str) -> Optional["BeautifulSoup"]:
        """Return a BeautifulSoup object or None if bs4 unavailable."""
        if not HAS_BS4:
            logger.error("BeautifulSoup4 not installed — cannot parse HTML")
            return None
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "html.parser")

    # ─────────────────────────────────────────────────────────────
    # ABSTRACT METHODS — implement in each subclass
    # ─────────────────────────────────────────────────────────────
    @abc.abstractmethod
    def search_horse(self, horse_name: str, country_code: str = "") -> Optional[str]:
        """
        Search for a horse on the target website.
        Returns the horse profile URL or None if not found.
        """

    @abc.abstractmethod
    def fetch_latest_run(self, horse_name: str, country_code: str = "") -> Optional[RaceRecord]:
        """
        Fetch the most recent completed race (or nearest upcoming entry).
        Returns a single RaceRecord or None.
        """

    @abc.abstractmethod
    def fetch_history(self, horse_name: str, country_code: str = "") -> list[RaceRecord]:
        """
        Fetch the full race history for a horse.
        Returns a list of RaceRecord (may be empty).
        """
