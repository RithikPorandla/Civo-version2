"""Ingest ISO-NE interconnection request queue for MA solar/BESS projects.

Scrapes the public IRTT (Interconnection Request Tracking Tool) portal at
irtt.iso-ne.com/reports/external — no login, no file download required.
The queue is rendered as an HTML table with 1,700+ entries updated weekly.

Usage:
    python -m ingest.isone_queue [--dry-run]
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone, date
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import SessionLocal

try:
    import pandas as pd
except ImportError:
    print("pandas required")
    sys.exit(1)

IRTT_URL = "https://irtt.iso-ne.com/reports/external"

# Fuel type codes → normalized project_type
_FUEL_MAP = {
    "SUN": "solar_ground_mount",
    "BAT": "bess_standalone",
    "WND": "wind",
    "NG":  "gas",
    "NUC": "nuclear",
    "HYD": "hydro",
    "OIL": "gas",
}

# Queue status codes → normalized status
_STATUS_MAP = {
    "AC": "active",
    "W":  "withdrawn",
    "CP": "completed",
    "SU": "suspended",
}


def _parse_date(val: str) -> date | None:
    if not val or val.strip() in ("", "N/A", "TBD", "0"):
        return None
    try:
        return datetime.strptime(val.strip(), "%m/%d/%Y").date()
    except Exception:
        return None


def scrape_queue() -> pd.DataFrame:
    """Fetch and parse the IRTT public queue table. Returns a DataFrame."""
    print(f"Fetching ISO-NE queue from {IRTT_URL} ...")
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True, timeout=60) as client:
        r = client.get(IRTT_URL)
        r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find(id="publicqueue")
    if not table:
        raise RuntimeError("Could not find #publicqueue table on IRTT page")

    headers = [th.text.strip() for th in table.find_all("th")]
    rows = []
    for tr in table.find_all("tr")[1:]:
        cells = [td.text.strip() for td in tr.find_all("td")]
        if cells:
            rows.append(cells)

    df = pd.DataFrame(rows, columns=headers)
    print(f"  Fetched {len(df)} queue entries, {len(headers)} columns")
    return df


def ingest(dry_run: bool = False) -> int:
    df = scrape_queue()

    # Filter to MA
    if "ST" in df.columns:
        df = df[df["ST"].str.upper().str.strip() == "MA"]
    elif "County" in df.columns:
        # Some entries have county but no state — keep all for MA filter below
        pass
    print(f"  MA entries: {len(df)}")

    if df.empty:
        print("  No MA entries found")
        return 0

    col = {c.lower(): c for c in df.columns}

    with SessionLocal() as session:
        inserted = 0
        for _, row in df.iterrows():
            qp = str(row.get(col.get("qp", "QP"), "")).strip()
            if not qp or qp in ("nan", ""):
                continue

            fuel = str(row.get(col.get("fuel type", "Fuel Type"), "")).strip().upper()
            ptype = _FUEL_MAP.get(fuel, "other")
            if ptype not in ("solar_ground_mount", "bess_standalone"):
                continue

            status_raw = str(row.get(col.get("status", "Status"), "AC")).strip().upper()
            status = _STATUS_MAP.get(status_raw, "active")

            try:
                mw = float(str(row.get(col.get("net mw", "Net MW"), "0")).replace(",", "") or 0)
            except (ValueError, TypeError):
                mw = None

            queue_id = f"ISONE-{qp}"
            name = str(row.get(col.get("alternative name", "Alternative Name"), "")).strip()
            county = str(row.get(col.get("county", "County"), "")).strip()
            op_date = _parse_date(str(row.get(col.get("op date", "Op Date"), "")))
            req_date = _parse_date(str(row.get(col.get("requested", "Requested"), "")))

            if dry_run:
                inserted += 1
                continue

            session.execute(text("""
                INSERT INTO isone_queue
                    (queue_id, project_name, town_name, county, state,
                     project_type, capacity_mw, queue_date, status,
                     in_service_date, ingested_at)
                VALUES
                    (:qid, :name, NULL, :county, 'MA',
                     :ptype, :mw, :qdate, :status,
                     :inservice, :now)
                ON CONFLICT (queue_id) DO UPDATE SET
                    status          = EXCLUDED.status,
                    in_service_date = EXCLUDED.in_service_date,
                    capacity_mw     = EXCLUDED.capacity_mw,
                    ingested_at     = EXCLUDED.ingested_at
            """), {
                "qid":      queue_id,
                "name":     name or None,
                "county":   county or None,
                "ptype":    ptype,
                "mw":       mw,
                "qdate":    req_date,
                "status":   status,
                "inservice": op_date,
                "now":      datetime.now(timezone.utc),
            })
            inserted += 1

        if not dry_run:
            session.commit()

    return inserted


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("ISO-NE Interconnection Queue ingest (IRTT public portal)")
    n = ingest(dry_run=args.dry_run)
    print(f"Done — {n} MA solar/BESS entries {'would be ' if args.dry_run else ''}ingested")


if __name__ == "__main__":
    main()
