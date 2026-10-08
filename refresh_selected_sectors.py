"""Interactive, cache-aware Sectors refresh for Watcher.

Run from the project root:
    python refresh_selected_sectors.py

The script reads backend/.env, asks for a key only when none is configured,
lets the operator choose a number of sectors, displays a conservative credit
estimate, and publishes one combined CSV snapshot for all companies in the
selected sectors. Existing request-cache entries are reused automatically.
"""
from __future__ import annotations

import getpass
import math
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def title_from_slug(value: str) -> str:
    special = {"it": "IT", "gas": "Gas", "oil": "Oil"}
    return " ".join(special.get(word, word.capitalize()) for word in value.split("-"))


def ask_integer(prompt: str, *, minimum: int, maximum: int) -> int:
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print("Enter a whole number.")
            continue
        if minimum <= value <= maximum:
            return value
        print(f"Choose a value from {minimum} to {maximum}.")


def ask_indices(count: int, total: int) -> list[int]:
    while True:
        raw = input(
            f"Choose exactly {count} sector number(s), comma-separated: "
        ).strip()
        try:
            selected = list(dict.fromkeys(int(value.strip()) for value in raw.split(",")))
        except ValueError:
            print("Use numbers separated by commas, for example: 2,4,7")
            continue
        if len(selected) != count or any(value < 1 or value > total for value in selected):
            print(f"Choose exactly {count} unique values from 1 to {total}.")
            continue
        return selected


def main() -> None:
    load_env(BACKEND / ".env")
    api_key = os.getenv("SECTORS_API_KEY", "").strip()
    if api_key.lower().startswith("bearer "):
        api_key = api_key[7:].strip()
    if not api_key:
        api_key = getpass.getpass("SECTORS_API_KEY is missing. Paste the key: ").strip()
        if not api_key:
            raise SystemExit("No API key supplied; no provider request was made.")
        os.environ["SECTORS_API_KEY"] = api_key

    from app.config import Settings
    from app.sectors_client import SectorsClient
    from app.weekly import WeeklyStore, read_csv, slug, utcnow

    settings = Settings.from_env()
    store = WeeklyStore(SectorsClient(settings))
    print("\nLoading the official Sectors taxonomy (cache is reused when available)...")
    taxonomy, _ = store.cached_request("/subsectors/", {}, 1)
    if not isinstance(taxonomy, list) or not taxonomy:
        raise SystemExit("Sectors returned an invalid taxonomy.")

    grouped: dict[str, list[dict]] = {}
    for entry in taxonomy:
        sector_slug = str(entry.get("sector", "")).strip()
        if sector_slug:
            grouped.setdefault(sector_slug, []).append(entry)
    sector_slugs = sorted(grouped)
    print("\nAvailable sectors")
    for index, sector_slug in enumerate(sector_slugs, start=1):
        print(
            f"  {index:>2}. {title_from_slug(sector_slug)} "
            f"({len(grouped[sector_slug])} subsectors)"
        )

    count = ask_integer(
        "\nHow many sectors should Watcher retrieve? ",
        minimum=1,
        maximum=len(sector_slugs),
    )
    indices = ask_indices(count, len(sector_slugs))
    chosen_slugs = [sector_slugs[index - 1] for index in indices]
    chosen_entries = [entry for key in chosen_slugs for entry in grouped[key]]

    print(
        f"\nPreflight needs up to {len(chosen_entries)} subsector-statistics calls "
        "to resolve official names and company counts."
    )
    if input("Continue with preflight? [y/N]: ").strip().lower() not in {"y", "yes"}:
        raise SystemExit("Cancelled before company reports were requested.")

    display_names: dict[str, str] = {}
    estimated_companies = 0
    for entry in chosen_entries:
        subsector_slug = str(entry["subsector"])
        report, _ = store.cached_request(
            f"/subsector/report/{subsector_slug}/",
            {"sections": "statistics"},
            1,
        )
        if slug(report.get("sector")) != entry["sector"]:
            raise SystemExit(f"Sector identity mismatch for {subsector_slug}.")
        display_names[entry["sector"]] = str(report["sector"])
        estimated_companies += int((report.get("statistics") or {}).get("total_companies") or 0)

    chosen_names = [display_names[value] for value in chosen_slugs]
    screener_pages = max(1, math.ceil(estimated_companies / 200))
    conservative_new_credits = (
        screener_pages + estimated_companies * store.client.section_cost
    )
    week = utcnow().strftime("%G-W%V")
    ledger = read_csv(store.root / "credits.csv")
    spent = sum(int(row["cost"]) for row in ledger if row.get("week") == week)
    configured_budget = int(os.getenv("WEEKLY_CREDIT_BUDGET", "550"))
    remaining = max(0, configured_budget - spent)

    print("\nRefresh plan")
    print(f"  Sectors: {', '.join(chosen_names)}")
    print(f"  Estimated companies: {estimated_companies}")
    print(f"  Report sections/company: {store.client.section_cost}")
    print(f"  Conservative remaining-request estimate: {conservative_new_credits} credits")
    print(f"  Current weekly ledger: {spent}/{configured_budget}; remaining {remaining}")
    print("  Fresh request-cache entries reduce the actual charge automatically.")

    allowed = ask_integer(
        "Maximum additional credits you authorize for this run: ",
        minimum=0,
        maximum=max(conservative_new_credits, remaining, 1_000_000),
    )
    if allowed == 0:
        raise SystemExit("Cancelled; no company report was requested.")
    if input('Type RUN to publish the new combined snapshot: ').strip() != "RUN":
        raise SystemExit("Cancelled; no company report was requested.")

    os.environ.update(
        {
            "COHORT_INDEX": "",
            "COHORT_SECTOR": "",
            "COHORT_SUBSECTOR": "",
            "COHORT_SECTORS": ",".join(chosen_names),
            "COHORT_SIZE": "0",
            "CACHE_ONLY_MODE": "false",
            "WEEKLY_CREDIT_BUDGET": str(spent + allowed),
        }
    )
    print("\nRefreshing. Safe request spacing and the durable CSV cache remain active...")
    store.refresh(force=True)
    status = store.status()
    print("\nWatcher snapshot published")
    print(f"  Version: {status.get('version')}")
    print(f"  Companies: {status.get('cohort_size')}")
    print(f"  Retrieved: {status.get('fetched_at')}")
    print(f"  Next due: {status.get('next_refresh_at')}")


if __name__ == "__main__":
    main()
