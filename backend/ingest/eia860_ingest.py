"""EIA Form 860 — utility-scale solar and battery storage ingest for Massachusetts.

Form 860 is the federal annual survey of all electric generators ≥1 MW.
Data is published by EIA as Excel workbooks (free, no API key):

    https://www.eia.gov/electricity/data/eia860/

Relevant sheets:
  3_1_Solar_Y{year}.xlsx        → utility-scale solar plants
  3_4_Energy_Storage_Y{year}.xlsx → battery storage facilities

Both sheets include: Plant Name, State, County, City, Street Address, Zip,
Latitude, Longitude, Status (OP=operating, P=planned, U=under construction),
Nameplate Capacity (MW), Owner name.

Status codes used as decision labels:
  OP  → "approved" (operational, i.e. fully permitted and built)
  SB  → "approved" (standby — still approved)
  P   → "pending" (planned, pre-permit)
  U   → "approved_with_conditions" (under construction — permitted, not yet operating)
  RE  → "withdrawn" (retired)
  T   → "pending" (proposed, in development)

Usage:
    python -m ingest.eia860_ingest --file data/eia860/3_1_Solar_Y2023.xlsx --type solar
    python -m ingest.eia860_ingest --file data/eia860/3_4_Energy_Storage_Y2023.xlsx --type bess
    python -m ingest.eia860_ingest --dir data/eia860/  # auto-detect both types

Alternatively, download latest via:
    python -m ingest.eia860_ingest --download --year 2023
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()
sys.path.insert(0, ".")
from app.db import SessionLocal

try:
    import pandas as pd
    import httpx
except ImportError:
    print("pandas and httpx are required: pip install pandas openpyxl httpx")
    sys.exit(1)

EIA860_BASE = "https://www.eia.gov/electricity/data/eia860/xls"
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "eia860"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# EIA status code → our decision value
STATUS_MAP = {
    "OP": "approved",
    "SB": "approved",
    "U":  "approved_with_conditions",
    "T":  "pending",
    "P":  "pending",
    "L":  "pending",
    "RE": "withdrawn",
    "V":  "withdrawn",
    "OA": "approved",
    "OS": "approved",
    "IP": "approved_with_conditions",
}


def _download_eia860(year: int) -> Path:
    """Download EIA 860 zip for given year and extract to data/eia860/."""
    url = f"{EIA860_BASE}/eia8602{year}.zip"
    print(f"  Downloading {url} ...")
    resp = httpx.get(url, timeout=120, follow_redirects=True)
    resp.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    zf.extractall(DATA_DIR)
    print(f"  Extracted to {DATA_DIR}")
    return DATA_DIR


def _load_solar(path: Path) -> pd.DataFrame:
    """Load solar sheet. Handles both old (Sheet1) and new multi-sheet formats."""
    for sheet in ["Operable", "Sheet1", "Operating"]:
        try:
            df = pd.read_excel(path, sheet_name=sheet, skiprows=1, dtype=str)
            if "Plant Name" in df.columns or "PLANT_NAME" in df.columns:
                return df
        except Exception:
            continue
    return pd.read_excel(path, skiprows=1, dtype=str)


def _load_storage(path: Path) -> pd.DataFrame:
    for sheet in ["Operable", "Sheet1", "Operating"]:
        try:
            df = pd.read_excel(path, sheet_name=sheet, skiprows=1, dtype=str)
            if "Plant Name" in df.columns or "Technology" in df.columns:
                return df
        except Exception:
            continue
    return pd.read_excel(path, skiprows=1, dtype=str)


def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to snake_case."""
    df.columns = [
        c.strip().lower()
         .replace(" ", "_")
         .replace("(", "")
         .replace(")", "")
         .replace("/", "_")
        for c in df.columns
    ]
    return df


_UPSERT = text("""
    INSERT INTO precedents
        (town_id, docket, project_type, project_address, applicant,
         decision, filing_date, decision_date, meeting_body,
         source_url, full_text, confidence, geom, created_at)
    VALUES (
        (SELECT town_id FROM municipalities WHERE UPPER(town_name) = UPPER(:town) LIMIT 1),
        :docket, :project_type, :address, :applicant,
        :decision, NULL, :decision_date,
        'eia_form_860',
        'https://www.eia.gov/electricity/data/eia860/',
        :full_text, :confidence,
        CASE WHEN :lat IS NOT NULL AND :lon IS NOT NULL
             THEN ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986)
             ELSE NULL END,
        :now
    )
    ON CONFLICT (docket) WHERE docket IS NOT NULL DO UPDATE SET
        decision      = EXCLUDED.decision,
        decision_date = EXCLUDED.decision_date
""")


def _ingest_df(
    df: pd.DataFrame,
    project_type: str,
    dry_run: bool,
) -> int:
    df = _normalize_cols(df)

    # Filter to Massachusetts
    state_col = next((c for c in df.columns if "state" in c and "name" not in c), None)
    if state_col:
        df = df[df[state_col].str.strip().str.upper() == "MA"]
    else:
        print("  Warning: no state column found — processing all rows")

    if df.empty:
        print("  No Massachusetts rows found.")
        return 0

    # Column aliases
    def _col(*candidates: str) -> str | None:
        for c in candidates:
            if c in df.columns:
                return c
        return None

    name_col    = _col("plant_name", "plant name", "generator_id")
    city_col    = _col("city", "county")
    addr_col    = _col("street_address", "street address", "address")
    status_col  = _col("status", "generator_status", "plant_status")
    cap_col     = _col("nameplate_capacity_mw", "nameplate_capacity", "total_capacity_mw")
    lat_col     = _col("latitude", "lat")
    lon_col     = _col("longitude", "lon")
    year_col    = _col("operating_year", "planned_operation_year", "retirement_year")
    owner_col   = _col("owner_name", "utility_name", "operator_name")

    count = 0
    with SessionLocal() as session:
        for _, row in df.iterrows():
            name = str(row.get(name_col, "")).strip() if name_col else ""
            city = str(row.get(city_col, "")).strip().title() if city_col else ""
            address = str(row.get(addr_col, "")).strip() if addr_col else ""
            status_raw = str(row.get(status_col, "")).strip().upper() if status_col else ""
            decision = STATUS_MAP.get(status_raw, "pending")

            # Only include definitively approved/operating projects as positive labels
            if status_raw not in ("OP", "SB", "U", "OA", "OS", "IP"):
                continue

            cap = None
            if cap_col:
                try:
                    cap = float(str(row[cap_col]).replace(",", ""))
                except (ValueError, TypeError):
                    pass

            lat_val, lon_val = None, None
            if lat_col and lon_col:
                try:
                    lat_val = float(str(row[lat_col]))
                    lon_val = float(str(row[lon_col]))
                except (ValueError, TypeError):
                    pass

            yr = None
            if year_col:
                try:
                    yr = int(float(str(row[year_col])))
                    decision_date: datetime | None = datetime(yr, 1, 1, tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    decision_date = None
            else:
                decision_date = None

            owner = str(row.get(owner_col, "")).strip() if owner_col else ""
            cap_str = f"{cap:.1f} MW" if cap else ""
            full_text = f"EIA Form 860: {project_type.upper()} project — {name}, {city}, MA. {cap_str}. Status: {status_raw}."
            docket = f"EIA860-{project_type[:4].upper()}-{name[:20].replace(' ', '_')}-{city}"[:60]

            if dry_run:
                print(f"    [dry-run] {name} | {city} | {decision} | {cap_str} | lat={lat_val}")
                count += 1
                continue

            session.execute(_UPSERT, {
                "town": city,
                "docket": docket,
                "project_type": project_type,
                "address": f"{address}, {city}, MA",
                "applicant": owner,
                "decision": decision,
                "decision_date": decision_date,
                "full_text": full_text,
                "confidence": 0.95,
                "lat": lat_val,
                "lon": lon_val,
                "now": datetime.now(timezone.utc),
            })
            count += 1

        if not dry_run:
            session.commit()

    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Path to EIA 860 Excel file")
    parser.add_argument("--dir", help="Directory containing EIA 860 files (auto-detect)")
    parser.add_argument("--type", choices=["solar", "bess"], help="Project type (required with --file)")
    parser.add_argument("--download", action="store_true", help="Download latest EIA 860 zip")
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.download:
        _download_eia860(args.year)

    files: list[tuple[Path, str]] = []

    if args.file:
        if not args.type:
            parser.error("--type is required with --file")
        files.append((Path(args.file), args.type))

    elif args.dir:
        d = Path(args.dir)
        for f in d.glob("*Solar*.xlsx"):
            files.append((f, "solar_ground_mount"))
        for f in d.glob("*Storage*.xlsx"):
            files.append((f, "bess_standalone"))
        for f in d.glob("*solar*.xlsx"):
            files.append((f, "solar_ground_mount"))
        for f in d.glob("*storage*.xlsx"):
            files.append((f, "bess_standalone"))

    elif args.download:
        for f in DATA_DIR.glob("*Solar*.xlsx"):
            files.append((f, "solar_ground_mount"))
        for f in DATA_DIR.glob("*Storage*.xlsx"):
            files.append((f, "bess_standalone"))
    else:
        parser.print_help()
        sys.exit(1)

    if not files:
        print("No EIA 860 Excel files found. Download with --download --year 2023")
        sys.exit(1)

    total = 0
    for path, ptype in files:
        print(f"Ingesting {path.name} as {ptype} ...")
        if "solar" in path.name.lower() or ptype == "solar_ground_mount":
            df = _load_solar(path)
        else:
            df = _load_storage(path)
        n = _ingest_df(df, ptype, dry_run=args.dry_run)
        print(f"  {n} rows ingested")
        total += n

    print(f"\nTotal: {total} EIA 860 rows ingested")


if __name__ == "__main__":
    main()
