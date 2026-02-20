"""
ShipStation Tracker
-------------------
Pulls order counts from the ShipStation V2 API and writes them to
C:\\WarehouseTracker\\orders_log.csv and combined_log.csv.

Usage (called by Windows Task Scheduler):
    python shipstation_tracker.py --mode morning     # 5:30 AM Mon-Thu
    python shipstation_tracker.py --mode afternoon   # 4:15 PM Mon-Thu

The script exits cleanly (code 0) on weekends/Fridays with no action.
Never run as a long-lived process — Task Scheduler fires it and it exits.
"""

import argparse
import csv
import os
import sys
from datetime import datetime, date
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
LOG_DIR = Path(r"C:\WarehouseTracker")
ORDERS_LOG = LOG_DIR / "orders_log.csv"
ACTIVITY_LOG = LOG_DIR / "activity_log.csv"
COMBINED_LOG = LOG_DIR / "combined_log.csv"

ORDERS_COLUMNS = ["Date", "Outstanding Orders", "Shipped Today"]
COMBINED_COLUMNS = ["Date", "First Click", "Last Click", "Outstanding Orders", "Shipped Today"]

SHIPSTATION_BASE = "https://api.shipstation.com/v2"

# Monday=0 … Thursday=3 are valid; Friday=4, Sat=5, Sun=6 are skipped
VALID_WEEKDAYS = {0, 1, 2, 3}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def _get_api_key() -> str:
    """Load API key from .env file (same directory as this script)."""
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)
    key = os.getenv("SHIPSTATION_API_KEY", "").strip()
    if not key:
        print("ERROR: SHIPSTATION_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)
    return key


def _api_headers(api_key: str) -> dict:
    return {
        "API-Key": api_key,
        "Content-Type": "application/json",
    }


def _fetch_order_count(api_key: str, params: dict) -> int:
    """
    Hit the V2 /orders endpoint and return the total record count.
    Fetches only 1 result per page — we only need the `total` from metadata.
    """
    params = {**params, "page_size": 1, "page": 1}
    url = f"{SHIPSTATION_BASE}/orders"
    resp = requests.get(url, headers=_api_headers(api_key), params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    # V2 returns: { "orders": [...], "total": N, "page": 1, "pages": N }
    return int(data.get("total", 0))


def get_awaiting_shipment_count(api_key: str) -> int:
    """Count all orders currently in 'awaiting_shipment' status."""
    return _fetch_order_count(api_key, {"order_status": "awaiting_shipment"})


def get_shipped_today_count(api_key: str) -> int:
    """Count orders shipped today (ship_date_start and ship_date_end = today)."""
    today_str = date.today().isoformat()  # YYYY-MM-DD
    return _fetch_order_count(api_key, {
        "order_status": "shipped",
        "ship_date_start": today_str,
        "ship_date_end": today_str,
    })


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------
def _ensure_orders_log() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not ORDERS_LOG.exists():
        with open(ORDERS_LOG, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=ORDERS_COLUMNS).writeheader()


def _read_csv(path: Path, columns: list[str]) -> list[dict]:
    """Read a CSV, returning a list of dicts. Returns empty list if file missing."""
    if not path.exists():
        return []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    """Atomically write rows to a CSV via a temp file."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def _upsert_orders_row(today: str, field: str, value: int) -> None:
    """Update a single column in today's orders_log row (create row if missing)."""
    _ensure_orders_log()
    rows = _read_csv(ORDERS_LOG, ORDERS_COLUMNS)

    today_row = None
    for row in rows:
        if row["Date"] == today:
            today_row = row
            break

    if today_row is None:
        today_row = {"Date": today, "Outstanding Orders": "", "Shipped Today": ""}
        rows.append(today_row)

    today_row[field] = str(value)
    _write_csv(ORDERS_LOG, ORDERS_COLUMNS, rows)


# ---------------------------------------------------------------------------
# combined_log.csv generation
# ---------------------------------------------------------------------------
def rebuild_combined_log() -> None:
    """
    Full outer-join activity_log.csv + orders_log.csv on Date.
    Writes combined_log.csv with columns:
        Date, First Click, Last Click, Outstanding Orders, Shipped Today
    activity_log columns 'First Activity'/'Last Activity' → 'First Click'/'Last Click'
    """
    activity_rows = _read_csv(ACTIVITY_LOG, ["Date", "First Activity", "Last Activity"])
    orders_rows = _read_csv(ORDERS_LOG, ORDERS_COLUMNS)

    # Index both by date
    activity_by_date: dict[str, dict] = {r["Date"]: r for r in activity_rows}
    orders_by_date: dict[str, dict] = {r["Date"]: r for r in orders_rows}

    all_dates = sorted(set(activity_by_date) | set(orders_by_date))

    combined: list[dict] = []
    for d in all_dates:
        act = activity_by_date.get(d, {})
        ord_ = orders_by_date.get(d, {})
        combined.append({
            "Date": d,
            "First Click": act.get("First Activity", ""),
            "Last Click": act.get("Last Activity", ""),
            "Outstanding Orders": ord_.get("Outstanding Orders", ""),
            "Shipped Today": ord_.get("Shipped Today", ""),
        })

    _write_csv(COMBINED_LOG, COMBINED_COLUMNS, combined)
    print(f"combined_log.csv rebuilt — {len(combined)} row(s).")


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------
def run_morning(api_key: str) -> None:
    """Pull awaiting_shipment count → Outstanding Orders column."""
    count = get_awaiting_shipment_count(api_key)
    today = date.today().isoformat()
    _upsert_orders_row(today, "Outstanding Orders", count)
    print(f"[Morning] {today}: Outstanding Orders = {count}")
    rebuild_combined_log()


def run_afternoon(api_key: str) -> None:
    """Pull shipped-today count → Shipped Today column."""
    count = get_shipped_today_count(api_key)
    today = date.today().isoformat()
    _upsert_orders_row(today, "Shipped Today", count)
    print(f"[Afternoon] {today}: Shipped Today = {count}")
    rebuild_combined_log()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="ShipStation order tracker")
    parser.add_argument(
        "--mode",
        choices=["morning", "afternoon"],
        required=True,
        help="morning = awaiting_shipment count; afternoon = shipped today count",
    )
    args = parser.parse_args()

    # Day-of-week guard — exit cleanly on Fri/Sat/Sun
    today_weekday = datetime.today().weekday()  # Mon=0, Sun=6
    if today_weekday not in VALID_WEEKDAYS:
        day_name = datetime.today().strftime("%A")
        print(f"Skipping — {day_name} is outside Mon–Thu window.")
        sys.exit(0)

    api_key = _get_api_key()

    if args.mode == "morning":
        run_morning(api_key)
    else:
        run_afternoon(api_key)


if __name__ == "__main__":
    main()
