"""
router.py - Routes each horse to the appropriate ordered list of scrapers
based on its country code.
"""

import importlib
import logging
from typing import Optional

from config import COUNTRY_SCRAPER_PRIORITY, SCRAPER_REGISTRY
from models import HorseInput

logger = logging.getLogger("horse_scraper.router")


def get_scraper_priority(country_code: str) -> list[str]:
    """
    Return the ordered list of scraper keys for a given country code.
    Falls back to DEFAULT if the country is unknown.
    """
    code = country_code.upper() if country_code else ""
    return COUNTRY_SCRAPER_PRIORITY.get(code, COUNTRY_SCRAPER_PRIORITY["DEFAULT"])


def enrich_horse_input(horse: HorseInput) -> HorseInput:
    """
    Attach the scraper priority list to a HorseInput based on its country code.
    """
    horse.scraper_priority = get_scraper_priority(horse.country_code)
    return horse


def load_scraper(scraper_key: str):
    """
    Dynamically load a scraper class by its registry key.

    Returns the instantiated scraper or None if unavailable.
    """
    info = SCRAPER_REGISTRY.get(scraper_key)
    if not info:
        logger.warning("No registry entry for scraper key: %s", scraper_key)
        return None

    module_name = info["module"]
    class_name = info["class"]

    # All scraper modules live in the scrapers/ package
    full_module = f"scrapers.{module_name}"
    try:
        mod = importlib.import_module(full_module)
        cls = getattr(mod, class_name)
        return cls()
    except ModuleNotFoundError:
        logger.debug("Scraper module not found: %s (skipping)", full_module)
        return None
    except AttributeError:
        logger.warning("Class %s not found in module %s", class_name, full_module)
        return None
    except Exception as exc:
        logger.error("Failed to load scraper %s: %s", scraper_key, exc)
        return None


def get_scrapers_for_horse(horse: HorseInput) -> list:
    """
    Return a list of instantiated scrapers for the given horse,
    in priority order, skipping any that fail to load.
    """
    scrapers = []
    for key in horse.scraper_priority:
        scraper = load_scraper(key)
        if scraper is not None:
            scrapers.append(scraper)
    return scrapers
