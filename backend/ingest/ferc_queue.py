"""Ingest FERC eQueue Activities file for historical ISO-NE interconnection data.

FERC publishes a quarterly Excel file covering all RTO/ISO interconnection
requests nationwide, going back to ~2000.  Filtering to ISO-NE gives 800+
completed/withdrawn solar and BESS projects — far more training data than
the MA-only IRTT scrape.

Download page:
    https://www.ferc.gov/media/equeue-activities

The file URL changes each quarter; this script fetches the page and finds
the current download link automatically.

Usage:
    python -m ingest.ferc_queue [--dry-run] [--file path/to/equeue.xlsx]
"""

from __future__ import annotations

import io
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import SessionLocal

try:
    import pandas as pd
except ImportError:
    print("pandas required: pip install pandas openpyxl")
    sys.exit(1)

FERC_PAGE_URL = "https://www.ferc.gov/media/equeue-activities"

# ISO-NE is listed under several names across file vintages
_ISONE_LABELS = {"iso-ne", "isone", "iso ne", "iso-new england", "iso new england"}

# Fuel → project_type
_FUEL_MAP = {
    "SUN": "solar_ground_mount",
    "BAT": "bess_standalone",
    "ES":  "bess_standalone",
    "WND": "wind",
    "NG":  "gas",
    "GAS": "gas",
    "NUC": "nuclear",
    "HYD": "hydro",
    "OIL": "gas",
    "PS":  "pumped_storage",
}

# FERC status → normalized
_STATUS_MAP = {
    "active":      "active",
    "in service":  "completed",
    "operational": "completed",
    "withdrawn":   "withdrawn",
    "suspended":   "suspended",
    "deactivated": "withdrawn",
}

_ISO_NE_STATES = {"MA", "CT", "RI", "NH", "VT", "ME"}


def _find_download_url() -> str:
    """Fetch the FERC eQueue page and extract the xlsx download link."""
    print(f"Fetching FERC eQueue page: {FERC_PAGE_URL}")
    resp = httpx.get(FERC_PAGE_URL, follow_redirects=True, timeout=30,
                     headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    matches = re.findall(r'href="([^"]+equeue[^"]*\.xlsx)"', resp.text, re.IGNORECASE)
    if not matches:
        # Try broader pattern
        matches = re.findall(r'href="([^"]+\.xlsx)"', resp.text, re.IGNORECASE)
    if not matches:
        raise RuntimeError("Could not find xlsx download link on FERC eQueue page")
    url = matches[0]
    if url.startswith("/"):
        url = "https://www.ferc.gov" + url
    print(f"  Found: {url}")
    return url


def _download_file(url: str) -> bytes:
    print(f"Downloading {url} ...")
    resp = httpx.get(url, follow_redirects=True, timeout=120,
                     headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    print(f"  Downloaded {len(resp.content) / 1_048_576:.1f} MB")
    return resp.content


def _normalize_cols(df: pd.DataFrame) -> dict[str, str]:
    """Return mapping from normalized key → actual column name."""
    return {c.strip().lower().replace(" ", "_").replace("/", "_"): c for c in df.columns}


def _parse_date(val: object) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if s in ("", "N/A", "TBD", "0", "nan"):
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y", "%B %d, %Y", "%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_mw(val: object) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _load_df(content: bytes) -> pd.DataFrame:
    """Load the FERC eQueue xlsx into a DataFrame.

    The file structure changes between vintages.  We try common sheet names
    and fall back to the first sheet.
    """
    xl = pd.ExcelFile(io.BytesIO(content))
    for sheet in xl.sheet_names:
        if any(k in sheet.lower() for k in ("queue", "active", "all", "data")):
            df = xl.parse(sheet, dtype=str)
            if len(df) > 100:
                print(f"  Using sheet '{sheet}' ({len(df)} rows)")
                return df
    # fallback
    df = xl.parse(xl.sheet_names[0], dtype=str)
    print(f"  Using first sheet '{xl.sheet_names[0]}' ({len(df)} rows)")
    return df


def _normalize_status(raw: str) -> str:
    r = raw.strip().lower()
    for k, v in _STATUS_MAP.items():
        if k in r:
            return v
    return "active"


def process_df(df: pd.DataFrame) -> pd.DataFrame:
    """Parse raw FERC eQueue DataFrame into normalized rows.

    Returns a DataFrame with columns:
        queue_id, project_name, iso_rto, state, county, project_type,
        capacity_mw, queue_date, status, in_service_date, withdrawn_date
    """
    col = _normalize_cols(df)

    def _get(df: pd.DataFrame, *keys: str) -> pd.Series | None:
        for k in keys:
            if k in col:
                return df[col[k]]
            # also try partial match
            for ck, cv in col.items():
                if k in ck:
                    return df[cv]
        return None

    iso_col  = _get(df, "iso_rto", "rto", "iso", "transmission_provider", "regional_transmission_organization")
    state_col = _get(df, "state", "st")
    county_col = _get(df, "county")
    qp_col   = _get(df, "queue_position", "qp", "project_number", "id")
    name_col = _get(df, "project_name", "name", "alternative_name")
    fuel_col = _get(df, "fuel", "fuel_type", "technology_type")
    status_col = _get(df, "status", "queue_status")
    mw_col   = _get(df, "capacity_mw", "net_mw", "mw", "nameplate_capacity_mw", "proposed_online_capacity_mw_ac")
    qdate_col = _get(df, "queue_date", "date_filed", "application_date", "requested")
    inservice_col = _get(df, "in_service_date", "actual_expected_in_service", "op_date", "expected_in_service_date")
    withdrawn_col = _get(df, "withdrawn_date", "withdrawal_date", "suspended_date")

    rows = []
    for i, row in df.iterrows():
        # ISO/RTO filter — keep only ISO-NE rows
        iso = str(iso_col.iloc[i] if iso_col is not None else "").strip().lower()
        state = str(state_col.iloc[i] if state_col is not None else "").strip().upper()

        is_isone = any(lbl in iso for lbl in _ISONE_LABELS)
        is_ne_state = state in _ISO_NE_STATES

        if not is_isone and not is_ne_state:
            continue

        qp = str(qp_col.iloc[i] if qp_col is not None else "").strip()
        if not qp or qp in ("nan", ""):
            continue

        fuel = str(fuel_col.iloc[i] if fuel_col is not None else "").strip().upper()
        ptype = _FUEL_MAP.get(fuel, "other")
        if ptype not in ("solar_ground_mount", "bess_standalone"):
            continue  # only train on solar + BESS

        status_raw = str(status_col.iloc[i] if status_col is not None else "").strip()
        status = _normalize_status(status_raw)

        rows.append({
            "queue_id":       f"FERC-{qp}",
            "project_name":   str(name_col.iloc[i] if name_col is not None else "").strip() or None,
            "iso_rto":        "ISO-NE" if is_isone else f"ISO-NE-inferred-{state}",
            "state":          state or None,
            "county":         str(county_col.iloc[i] if county_col is not None else "").strip() or None,
            "project_type":   ptype,
            "capacity_mw":    _parse_mw(mw_col.iloc[i] if mw_col is not None else None),
            "queue_date":     _parse_date(qdate_col.iloc[i] if qdate_col is not None else None),
            "status":         status,
            "in_service_date": _parse_date(inservice_col.iloc[i] if inservice_col is not None else None),
            "withdrawn_date": _parse_date(withdrawn_col.iloc[i] if withdrawn_col is not None else None),
        })

    return pd.DataFrame(rows)


def ingest(content: bytes, dry_run: bool = False) -> int:
    df = process_df(_load_df(content))
    print(f"  ISO-NE solar/BESS rows after filtering: {len(df)}")

    status_counts = df["status"].value_counts().to_dict()
    print(f"  Status breakdown: {status_counts}")

    if dry_run:
        print(df.head(5).to_string())
        return len(df)

    inserted = 0
    with SessionLocal() as session:
        for _, row in df.iterrows():
            if pd.isna(row.get("queue_date") or float("nan")):
                continue  # queue_date is required for training

            session.execute(text("""
                INSERT INTO ferc_queue
                    (queue_id, project_name, iso_rto, state, county,
                     project_type, capacity_mw, queue_date, status,
                     in_service_date, withdrawn_date, source_year, ingested_at)
                VALUES
                    (:qid, :name, :iso, :state, :county,
                     :ptype, :mw, :qdate, :status,
                     :inservice, :withdrawn, :yr, :now)
                ON CONFLICT (queue_id) DO UPDATE SET
                    status           = EXCLUDED.status,
                    in_service_date  = EXCLUDED.in_service_date,
                    withdrawn_date   = EXCLUDED.withdrawn_date,
                    capacity_mw      = EXCLUDED.capacity_mw,
                    ingested_at      = EXCLUDED.ingested_at
            """), {
                "qid":      row["queue_id"],
                "name":     row["project_name"],
                "iso":      row["iso_rto"],
                "state":    row["state"],
                "county":   row["county"],
                "ptype":    row["project_type"],
                "mw":       row["capacity_mw"],
                "qdate":    row["queue_date"],
                "status":   row["status"],
                "inservice": row["in_service_date"],
                "withdrawn": row["withdrawn_date"],
                "yr":       row["queue_date"].year if row["queue_date"] else None,
                "now":      datetime.now(timezone.utc),
            })
            inserted += 1

        session.commit()

    return inserted


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", help="Path to local FERC eQueue xlsx (skip download)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.file:
        content = Path(args.file).read_bytes()
    else:
        url = _find_download_url()
        content = _download_file(url)

    n = ingest(content, dry_run=args.dry_run)
    print(f"Done — {n} ISO-NE solar/BESS rows {'would be ' if args.dry_run else ''}ingested")


if __name__ == "__main__":
    main()
