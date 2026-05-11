"""
main.py - Horse Racing Data Scraper
=====================================
Entry point for the horse racing scraper application.

Supports:
  - Manual horse name entry (single or comma/newline separated)
  - Excel import (horse names in first column, e.g. "Forever Young (JPN)")
  - Country-aware routing to prioritised scrapers
  - Concurrent scraping with ThreadPoolExecutor
  - Rich console progress and logging
  - Two Excel exports: latest run + full history
  - Google Colab compatible

Usage:
  python main.py
  python main.py --input horses.xlsx
  python main.py --horse "Equinox (JPN), Romantic Warrior (IRE)"
"""

# ── Colab / Jupyter compatibility ──────────────────────────────────────────
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass   # Not in Colab / Jupyter

# ── Standard library ───────────────────────────────────────────────────────
import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

# ── Ensure project root is on sys.path (important for Colab) ───────────────
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ── Third-party ────────────────────────────────────────────────────────────
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("WARNING: pandas not installed. Excel import disabled.")

try:
    from rich.console import Console
    from rich.progress import (
        Progress,
        SpinnerColumn,
        BarColumn,
        TextColumn,
        TimeElapsedColumn,
        MofNCompleteColumn,
    )
    from rich.panel import Panel
    from rich.text import Text
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# ── Internal modules ────────────────────────────────────────────────────────
from config import (
    MAX_WORKERS,
    OUTPUT_DIR,
    LOGS_DIR,
    CACHE_DIR,
)
from models import HorseInput, RaceRecord
from logging_utils import setup_logging, get_logger
from horse_name_utils import parse_horse_name, deduplicate_horses
from router import enrich_horse_input, get_scrapers_for_horse
from excel_utils import export_latest_run, export_history

# ── Logger ─────────────────────────────────────────────────────────────────
logger = get_logger("main")
_console = Console() if HAS_RICH else None


# ═══════════════════════════════════════════════════════════════════════════
# STARTUP BANNER
# ═══════════════════════════════════════════════════════════════════════════

def print_banner() -> None:
    """Print a styled startup banner."""
    if HAS_RICH and _console:
        banner = Text()
        banner.append("🏇  HORSE RACING DATA SCRAPER  🏇\n", style="bold white on dark_blue")
        banner.append("    Fetch · Normalise · Export    \n", style="dim white on dark_blue")
        _console.print(Panel(banner, border_style="blue", padding=(0, 2)))
        _console.print()
    else:
        print("=" * 50)
        print("   HORSE RACING DATA SCRAPER")
        print("=" * 50)


# ═══════════════════════════════════════════════════════════════════════════
# ENVIRONMENT DETECTION
# ═══════════════════════════════════════════════════════════════════════════

def is_colab() -> bool:
    """Detect if running in Google Colab."""
    try:
        import google.colab  # noqa
        return True
    except ImportError:
        return False


def is_jupyter() -> bool:
    """Detect if running in a Jupyter notebook."""
    try:
        from IPython import get_ipython
        return get_ipython() is not None
    except ImportError:
        return False


def colab_install_dependencies() -> None:
    """
    Install missing dependencies automatically in Colab.
    Runs pip install silently.
    """
    if not is_colab():
        return

    packages = [
        "cloudscraper", "beautifulsoup4", "rapidfuzz",
        "tenacity", "rich", "nest-asyncio", "openpyxl",
        "playwright", "lxml",
    ]
    missing = []
    for pkg in packages:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            missing.append(pkg)

    if missing:
        logger.info("Colab: installing missing packages: %s", ", ".join(missing))
        import subprocess
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q"] + missing,
            check=False
        )
        # Install playwright browser
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=False,
                capture_output=True,
            )
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# INPUT COLLECTION
# ═══════════════════════════════════════════════════════════════════════════

def collect_horse_names_interactive() -> list[str]:
    """
    Interactive menu: let user choose manual entry or Excel import.
    Returns a raw list of horse name strings.
    """
    if HAS_RICH and _console:
        _console.print(
            Panel(
                "[bold cyan]How would you like to provide horse names?[/bold cyan]\n\n"
                "  [bold yellow][1][/bold yellow]  Manual entry  "
                "(e.g. Equinox (JPN), Romantic Warrior (IRE))\n"
                "  [bold yellow][2][/bold yellow]  Import from Excel file",
                border_style="cyan",
                title="Input Method",
            )
        )
    else:
        print("\nHow would you like to provide horse names?")
        print("  [1] Manual entry")
        print("  [2] Import from Excel file")

    choice = input("\nEnter choice [1/2]: ").strip()

    if choice == "2":
        return _collect_from_excel()
    else:
        return _collect_manual()


def _collect_manual() -> list[str]:
    """
    Collect horse names from manual keyboard input.
    Accepts comma-separated or one-per-line input.
    """
    if HAS_RICH and _console:
        _console.print(
            "\n[dim]Enter horse names (comma-separated or one per line).[/dim]"
            "\n[dim]Include country code in brackets: Forever Young (JPN)[/dim]"
            "\n[dim]Press Enter twice (blank line) when done.[/dim]\n"
        )
    else:
        print("\nEnter horse names (comma-separated or one per line).")
        print("Include country code: Forever Young (JPN)")
        print("Press Enter twice when done.\n")

    lines = []
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            # Non-interactive environment (piped input)
            break
        if not line:
            if lines:
                break
            continue
        lines.append(line)

    # Flatten: split by comma and newline
    raw_names = []
    for line in lines:
        parts = [p.strip() for p in line.replace(",", "\n").split("\n") if p.strip()]
        raw_names.extend(parts)

    return raw_names


def _collect_from_excel(filepath: Optional[str] = None) -> list[str]:
    """
    Read horse names from the first column of an Excel file.

    Args:
        filepath: Path to the Excel file. If None, prompts the user.

    Returns:
        List of raw horse name strings.
    """
    if not HAS_PANDAS:
        logger.error("pandas is required for Excel import. Install with: pip install pandas openpyxl")
        return []

    if not filepath:
        if HAS_RICH and _console:
            _console.print("\n[cyan]Enter path to the Excel file:[/cyan]")
        else:
            print("\nEnter path to the Excel file:")
        filepath = input("> ").strip().strip('"').strip("'")

    if not os.path.exists(filepath):
        logger.error("File not found: %s", filepath)
        return []

    try:
        # Read first column, skip empty cells
        df = pd.read_excel(filepath, header=0, usecols=[0], dtype=str)
        col = df.columns[0]
        names = df[col].dropna().astype(str).str.strip().tolist()
        names = [n for n in names if n and n.lower() not in ("horse name", "horse", "name")]
        logger.info("Loaded %d horse names from %s", len(names), filepath)
        return names
    except Exception as exc:
        logger.error("Failed to read Excel file '%s': %s", filepath, exc)
        return []


def parse_horse_inputs(raw_names: list[str]) -> list[HorseInput]:
    """
    Convert raw name strings into HorseInput objects with routing data.

    Steps:
    1. Deduplicate
    2. Parse name + country code
    3. Attach scraper priority list
    """
    # Deduplicate at raw string level first
    unique = list(dict.fromkeys(n.strip() for n in raw_names if n.strip()))

    inputs = []
    for raw in unique:
        clean_name, country_code = parse_horse_name(raw)
        if not clean_name:
            logger.warning("Skipping empty horse name from: '%s'", raw)
            continue

        horse = HorseInput(
            raw_name=raw,
            clean_name=clean_name,
            country_code=country_code,
        )
        horse = enrich_horse_input(horse)
        inputs.append(horse)

    # Fuzzy deduplication across clean names
    seen_names: list[str] = []
    deduped = []
    for horse in inputs:
        from horse_name_utils import is_same_horse
        if not any(is_same_horse(horse.clean_name, s) for s in seen_names):
            seen_names.append(horse.clean_name)
            deduped.append(horse)
        else:
            logger.info("Deduplicating: '%s' (already seen)", horse.clean_name)

    logger.info("Processing %d unique horses", len(deduped))
    return deduped


# ═══════════════════════════════════════════════════════════════════════════
# SCRAPING ENGINE
# ═══════════════════════════════════════════════════════════════════════════

def scrape_horse(horse: HorseInput) -> dict:
    """
    Scrape a single horse: latest run + full history.

    Tries each scraper in priority order, stopping on the first
    that returns data.

    Returns:
        {
            "horse":   HorseInput,
            "latest":  RaceRecord | None,
            "upcoming": list[RaceRecord],
            "history": list[RaceRecord],
            "errors":  list[str],
        }
    """
    result = {
        "horse":    horse,
        "latest":   None,
        "upcoming": [],
        "history":  [],
        "errors":   [],
    }

    scrapers = get_scrapers_for_horse(horse)
    if not scrapers:
        msg = f"No scrapers available for {horse.clean_name} ({horse.country_code})"
        logger.warning(msg)
        result["errors"].append(msg)
        return result

    logger.info(
        "Scraping '%s' [%s] — trying: %s",
        horse.clean_name,
        horse.country_code or "??",
        ", ".join(s.name for s in scrapers),
    )

    # ── Latest run ────────────────────────────────────────────────────────
    for scraper in scrapers:
        try:
            rec = scraper.fetch_latest_run(horse.clean_name, horse.country_code)
            if rec:
                result["latest"] = rec
                logger.info(
                    "  ✓ Latest run for '%s': %s via %s",
                    horse.clean_name, rec.race_date, scraper.name
                )
                break
        except Exception as exc:
            err = f"{scraper.name} latest_run error: {exc}"
            logger.debug(err)
            result["errors"].append(err)

    if result["latest"] is None:
        logger.warning("  ✗ No latest run found for '%s'", horse.clean_name)

    # ── Full history ──────────────────────────────────────────────────────
    for scraper in scrapers:
        try:
            records = scraper.fetch_history(horse.clean_name, horse.country_code)
            if records:
                result["history"] = records
                logger.info(
                    "  ✓ History for '%s': %d records via %s",
                    horse.clean_name, len(records), scraper.name
                )
                break
        except Exception as exc:
            err = f"{scraper.name} history error: {exc}"
            logger.debug(err)
            result["errors"].append(err)

    if not result["history"]:
        # If we got a latest run, use it as the minimal history
        if result["latest"]:
            result["history"] = [result["latest"]]
        else:
            logger.warning("  ✗ No history found for '%s'", horse.clean_name)

    # ── Upcoming (separate from latest) ──────────────────────────────────
    # Upcoming races are already mixed into history/latest from scrapers
    # that return UPCOMING status. Extract them for the upcoming sheet.
    all_records = result["history"]
    result["upcoming"] = [r for r in all_records if r.race_status == "UPCOMING"]

    return result


def scrape_all_horses(
    horses: list[HorseInput],
    max_workers: int = MAX_WORKERS,
) -> tuple[list[RaceRecord], list[RaceRecord]]:
    """
    Scrape all horses concurrently.

    Returns:
        (latest_records, all_history_records)
    """
    all_latest: list[RaceRecord] = []
    all_history: list[RaceRecord] = []

    if HAS_RICH and _console:
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=_console,
            transient=False,
        )
        task = progress.add_task(
            f"[cyan]Scraping {len(horses)} horse(s)...", total=len(horses)
        )
    else:
        progress = None
        task = None

    futures_map = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for horse in horses:
            future = executor.submit(scrape_horse, horse)
            futures_map[future] = horse

        if progress:
            progress.start()

        for future in as_completed(futures_map):
            horse = futures_map[future]
            try:
                result = future.result()
            except Exception as exc:
                logger.error("Unhandled error scraping '%s': %s", horse.clean_name, exc)
                if progress and task is not None:
                    progress.advance(task)
                continue

            # Collect results
            if result["latest"]:
                all_latest.append(result["latest"])
            all_history.extend(result["history"])

            # Status update
            latest_date = result["latest"].race_date if result["latest"] else "—"
            history_count = len(result["history"])
            status_line = (
                f"'{horse.clean_name}' → latest: {latest_date}, "
                f"history: {history_count} records"
            )
            if progress and task is not None:
                progress.advance(task)
                progress.console.log(f"[green]✓[/green] {status_line}")
            else:
                print(f"✓ {status_line}")

            # Log any errors at debug level
            for err in result.get("errors", []):
                logger.debug("  [error] %s", err)

    if progress:
        progress.stop()

    logger.info(
        "Scraping complete — %d latest records, %d history records",
        len(all_latest), len(all_history)
    )
    return all_latest, all_history


# ═══════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════

def export_results(
    latest_records: list[RaceRecord],
    history_records: list[RaceRecord],
) -> tuple[Optional[str], Optional[str]]:
    """
    Export results to Excel files.

    Returns:
        (latest_filepath, history_filepath)
    """
    latest_path = None
    history_path = None

    if latest_records:
        try:
            latest_path = export_latest_run(latest_records)
            if HAS_RICH and _console:
                _console.print(f"[bold green]✓ Latest run saved:[/bold green] {latest_path}")
            else:
                print(f"✓ Latest run saved: {latest_path}")
        except Exception as exc:
            logger.error("Failed to export latest run: %s", exc)
    else:
        logger.warning("No latest run records to export")

    if history_records:
        try:
            history_path = export_history(history_records)
            if HAS_RICH and _console:
                _console.print(f"[bold green]✓ History saved:[/bold green] {history_path}")
            else:
                print(f"✓ History saved: {history_path}")
        except Exception as exc:
            logger.error("Failed to export history: %s", exc)
    else:
        logger.warning("No history records to export")

    return latest_path, history_path


# ═══════════════════════════════════════════════════════════════════════════
# CLI ARGUMENT PARSER
# ═══════════════════════════════════════════════════════════════════════════

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Horse Racing Data Scraper — fetch and export race data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --horse "Equinox (JPN)"
  python main.py --horse "Equinox (JPN), Romantic Warrior (IRE)"
  python main.py --input horses.xlsx
  python main.py --workers 6 --log-level DEBUG
        """,
    )
    parser.add_argument(
        "--horse", "-H",
        type=str,
        default=None,
        help="Horse name(s), comma-separated. e.g. 'Equinox (JPN), Romantic Warrior (IRE)'",
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=None,
        help="Path to Excel file containing horse names in column A",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=MAX_WORKERS,
        help=f"Number of concurrent workers (default: {MAX_WORKERS})",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable local response cache",
    )
    return parser


# ═══════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Main application logic."""

    # ── Parse CLI args ────────────────────────────────────────────────────
    parser = build_arg_parser()
    # In Colab/Jupyter, sys.argv may contain notebook arguments — handle gracefully
    try:
        args = parser.parse_args()
    except SystemExit:
        # Non-CLI environment (Colab): use defaults
        args = argparse.Namespace(
            horse=None,
            input=None,
            workers=MAX_WORKERS,
            log_level="INFO",
            no_cache=False,
        )

    # ── Logging ───────────────────────────────────────────────────────────
    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    setup_logging(level=log_level)

    # ── Colab dependency check ────────────────────────────────────────────
    colab_install_dependencies()

    # ── Banner ────────────────────────────────────────────────────────────
    print_banner()

    env = "Google Colab" if is_colab() else ("Jupyter" if is_jupyter() else "Terminal")
    logger.info("Running in: %s", env)
    logger.info("Output directory: %s", OUTPUT_DIR)

    # ── Collect horse names ───────────────────────────────────────────────
    raw_names: list[str] = []

    if args.horse:
        # CLI: --horse "Name1, Name2"
        raw_names = [n.strip() for n in args.horse.split(",") if n.strip()]
        logger.info("CLI input: %d horse(s)", len(raw_names))

    elif args.input:
        # CLI: --input file.xlsx
        raw_names = _collect_from_excel(args.input)

    else:
        # Interactive mode
        raw_names = collect_horse_names_interactive()

    if not raw_names:
        logger.error("No horse names provided. Exiting.")
        sys.exit(1)

    if HAS_RICH and _console:
        _console.print(
            f"\n[bold]Processing [cyan]{len(raw_names)}[/cyan] horse name(s):[/bold]"
        )
        for name in raw_names:
            _console.print(f"  • {name}")
        _console.print()
    else:
        print(f"\nProcessing {len(raw_names)} horse(s):")
        for name in raw_names:
            print(f"  - {name}")

    # ── Parse + route ─────────────────────────────────────────────────────
    horses = parse_horse_inputs(raw_names)
    if not horses:
        logger.error("No valid horse inputs after parsing. Exiting.")
        sys.exit(1)

    # ── Scrape ────────────────────────────────────────────────────────────
    start_time = time.time()

    if HAS_RICH and _console:
        _console.rule("[bold blue]Starting scrape")

    latest_records, history_records = scrape_all_horses(
        horses, max_workers=args.workers
    )

    elapsed = time.time() - start_time

    # ── Export ────────────────────────────────────────────────────────────
    if HAS_RICH and _console:
        _console.rule("[bold green]Exporting results")

    latest_path, history_path = export_results(latest_records, history_records)

    # ── Summary ───────────────────────────────────────────────────────────
    if HAS_RICH and _console:
        _console.print()
        _console.print(
            Panel(
                f"[bold]✅ Scrape complete in [cyan]{elapsed:.1f}s[/cyan][/bold]\n\n"
                f"  Horses processed : [yellow]{len(horses)}[/yellow]\n"
                f"  Latest records   : [yellow]{len(latest_records)}[/yellow]\n"
                f"  History records  : [yellow]{len(history_records)}[/yellow]\n\n"
                + (f"  📄 Latest run  → [cyan]{latest_path}[/cyan]\n" if latest_path else "")
                + (f"  📄 History     → [cyan]{history_path}[/cyan]\n" if history_path else ""),
                border_style="green",
                title="Summary",
            )
        )
    else:
        print(f"\n{'='*50}")
        print(f"Scrape complete in {elapsed:.1f}s")
        print(f"Horses processed : {len(horses)}")
        print(f"Latest records   : {len(latest_records)}")
        print(f"History records  : {len(history_records)}")
        if latest_path:
            print(f"Latest run  → {latest_path}")
        if history_path:
            print(f"History     → {history_path}")
        print("=" * 50)

    # ── Colab: make files downloadable ────────────────────────────────────
    if is_colab():
        try:
            from google.colab import files
            for path in [latest_path, history_path]:
                if path and os.path.exists(path):
                    logger.info("Colab: offering download for %s", path)
                    files.download(path)
        except Exception as exc:
            logger.debug("Colab download trigger failed: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
# COLAB HELPER FUNCTION
# (Users can call this directly from a Colab cell)
# ═══════════════════════════════════════════════════════════════════════════

def run_in_colab(
    horse_names: Optional[list[str]] = None,
    excel_path: Optional[str] = None,
    workers: int = 3,
) -> tuple[Optional[str], Optional[str]]:
    """
    Convenience function for running inside Google Colab cells.

    Usage in a Colab cell:
        from main import run_in_colab
        run_in_colab(["Equinox (JPN)", "Romantic Warrior (IRE)"])

    Args:
        horse_names: List of horse name strings (with or without country codes)
        excel_path:  Path to Excel file with horse names in column A
        workers:     Number of concurrent scraping threads

    Returns:
        (latest_excel_path, history_excel_path)
    """
    setup_logging()
    colab_install_dependencies()

    raw_names: list[str] = []

    if horse_names:
        raw_names = [n.strip() for n in horse_names if n.strip()]
    elif excel_path:
        raw_names = _collect_from_excel(excel_path)
    else:
        raw_names = collect_horse_names_interactive()

    if not raw_names:
        logger.error("No horse names provided.")
        return None, None

    horses = parse_horse_inputs(raw_names)
    if not horses:
        logger.error("No valid horses after parsing.")
        return None, None

    latest_records, history_records = scrape_all_horses(horses, max_workers=workers)
    return export_results(latest_records, history_records)


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
