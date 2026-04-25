"""MA DEP eDEP WPA (Wetlands Protection Act) decision scraper.

Scrapes ConCom Orders of Conditions and Denial decisions for solar and
battery storage projects from the public eDEP portal. Upserts into the
precedents table with parcel matching via address geocoding.

Sources:
  Primary  : https://edep.dep.state.ma.us/pages/WPA/WPASearch.aspx
             (ASP.NET WebForms — handles viewstate automatically)
  Geocoding: Nominatim OSM (no API key required; 1 req/sec limit)
  Parcel   : ST_DWithin match on geocoded point vs parcels.geom

Usage:
    python -m ingest.edep_scraper --town Acton
    python -m ingest.edep_scraper --all-towns --start-year 2020
    python -m ingest.edep_scraper --all-towns --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()
sys.path.insert(0, ".")
from app.db import SessionLocal

# ── Constants ─────────────────────────────────────────────────────────────────

EDEP_BASE = "https://edep.dep.state.ma.us"
EDEP_SEARCH = f"{EDEP_BASE}/pages/WPA/WPASearch.aspx"
EDEP_DETAIL = f"{EDEP_BASE}/pages/WPA/WPAView.aspx"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache" / "edep"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Keywords that indicate a solar or BESS project in the project description
SOLAR_BESS_KEYWORDS = re.compile(
    r"\b(solar|photovoltaic|pv panel|pv array|bess|battery|energy storage|ground.mount)\b",
    re.I,
)

# Map eDEP activity labels → our decision values
ACTIVITY_DECISION_MAP: dict[str, str] = {
    "order of conditions":        "approved_with_conditions",
    "denial":                     "denied",
    "superseding order":          "approved_with_conditions",
    "superseding denial":         "denied",
    "determination of applicability": "approved",
    "negative determination":     "denied",
    "certificate of compliance":  "approved",
}

# Map eDEP activity labels → meeting_body
ACTIVITY_BODY_MAP: dict[str, str] = {
    "order of conditions":        "conservation_commission",
    "denial":                     "conservation_commission",
    "superseding order":          "dep",
    "superseding denial":         "dep",
    "determination of applicability": "conservation_commission",
    "negative determination":     "conservation_commission",
    "certificate of compliance":  "conservation_commission",
}

HEADERS = {
    "User-Agent": "Civo-Permitting-Intelligence/1.0 (research@civo.ai; respectful scraper)",
    "Accept": "text/html,application/xhtml+xml",
}


# ── ViewState Helper ──────────────────────────────────────────────────────────

def _get_viewstate(client: httpx.Client) -> dict[str, str]:
    """GET the search page and extract ASP.NET hidden form fields."""
    resp = client.get(EDEP_SEARCH, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    state: dict[str, str] = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        tag = soup.find("input", {"name": name})
        if tag:
            state[name] = tag.get("value", "")
    return state


def _parse_town_options(client: httpx.Client) -> dict[str, str]:
    """Return {display_name: option_value} for the town dropdown."""
    resp = client.get(EDEP_SEARCH, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(resp.text, "lxml")
    select = soup.find("select", {"id": re.compile(r"ddlTown", re.I)})
    if not select:
        return {}
    return {
        opt.get_text(strip=True).upper(): opt.get("value", "")
        for opt in select.find_all("option")
        if opt.get("value")
    }


# ── Search ────────────────────────────────────────────────────────────────────

def _search_town(
    client: httpx.Client,
    town_value: str,
    start_date: str,
    end_date: str,
    activity_value: str = "",
) -> list[dict]:
    """POST the WPA search form and return parsed result rows."""
    viewstate = _get_viewstate(client)
    time.sleep(1)

    form_data = {
        **viewstate,
        "ctl00$MainContent$ddlTown": town_value,
        "ctl00$MainContent$ddlActivity": activity_value,
        "ctl00$MainContent$txtStartDate": start_date,
        "ctl00$MainContent$txtEndDate": end_date,
        "ctl00$MainContent$btnSearch": "Search",
    }
    resp = client.post(EDEP_SEARCH, data=form_data, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    time.sleep(1)
    return _parse_results_table(resp.text)


def _parse_results_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", {"id": re.compile(r"gvResults|GridView|resultsGrid", re.I)})
    if not table:
        # Try any table with the expected column headers
        for tbl in soup.find_all("table"):
            headers_row = tbl.find("tr")
            if headers_row and re.search(r"dep.?file|applicant", headers_row.get_text(), re.I):
                table = tbl
                break

    if not table:
        return []

    rows = table.find_all("tr")
    if not rows:
        return []

    # Extract column mapping from header row
    header_cells = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]
    col: dict[str, int] = {}
    for i, h in enumerate(header_cells):
        if "dep" in h and "file" in h:
            col["dep_file"] = i
        elif "town" in h:
            col["town"] = i
        elif "applicant" in h:
            col["applicant"] = i
        elif "address" in h or "project" in h and "addr" in h:
            col["address"] = i
        elif "activity" in h or "type" in h:
            col["activity"] = i
        elif "date" in h or "status" in h:
            col["date"] = i
        elif "desc" in h:
            col["description"] = i

    results = []
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            continue

        def _cell(key: str) -> str:
            idx = col.get(key)
            return cells[idx].get_text(strip=True) if idx is not None and idx < len(cells) else ""

        # Extract detail page link (usually on DEP file number or first cell)
        detail_link = None
        for cell in cells:
            a = cell.find("a", href=True)
            if a and "WPAView" in a["href"]:
                detail_link = EDEP_BASE + a["href"] if a["href"].startswith("/") else a["href"]
                break

        results.append({
            "dep_file": _cell("dep_file"),
            "town": _cell("town"),
            "applicant": _cell("applicant"),
            "address": _cell("address"),
            "activity": _cell("activity"),
            "description": _cell("description"),
            "status_date": _cell("date"),
            "detail_url": detail_link,
        })

    return results


# ── Detail Page ───────────────────────────────────────────────────────────────

def _fetch_detail(client: httpx.Client, url: str) -> dict:
    """Fetch a WPA detail page and extract project description + full text."""
    cache_key = CACHE_DIR / (re.sub(r"[^a-z0-9]", "_", url.lower()) + ".json")
    if cache_key.exists():
        return json.loads(cache_key.read_text())

    try:
        resp = client.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        time.sleep(1)
    except Exception:
        return {}

    soup = BeautifulSoup(resp.text, "lxml")
    # Grab all visible text as full_text; extract description from known fields
    description = ""
    for label in soup.find_all(string=re.compile(r"project.?desc|description", re.I)):
        parent = label.find_parent()
        if parent:
            sibling = parent.find_next_sibling()
            if sibling:
                description = sibling.get_text(" ", strip=True)
                break

    full_text = soup.get_text(" ", strip=True)[:4000]
    result = {"description": description, "full_text": full_text}
    cache_key.write_text(json.dumps(result))
    return result


# ── Geocoding ─────────────────────────────────────────────────────────────────

_GEO_CACHE_PATH = CACHE_DIR / "nominatim_cache.json"
_geo_cache: dict[str, tuple[float, float] | None] = (
    json.loads(_GEO_CACHE_PATH.read_text()) if _GEO_CACHE_PATH.exists() else {}
)


def _geocode(address: str, town: str) -> tuple[float, float] | None:
    query = f"{address}, {town}, MA"
    if query in _geo_cache:
        return _geo_cache[query]

    try:
        resp = httpx.get(
            NOMINATIM,
            params={"q": query, "format": "json", "countrycodes": "us", "limit": 1},
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=10,
        )
        data = resp.json()
        if data:
            result: tuple[float, float] | None = (float(data[0]["lat"]), float(data[0]["lon"]))
        else:
            result = None
    except Exception:
        result = None

    _geo_cache[query] = result
    _GEO_CACHE_PATH.write_text(json.dumps(_geo_cache))
    time.sleep(1.1)  # Nominatim 1 req/sec policy
    return result


# ── Parcel Matching ───────────────────────────────────────────────────────────

def _find_parcel(session, lat: float, lon: float, address: str, town: str) -> str | None:
    """Find nearest parcel within 100m by geocoded point, or 500m if address hint matches."""
    # Try exact address match first
    if address:
        addr_row = session.execute(
            text("""
                SELECT loc_id FROM parcels
                WHERE town_name = :town
                  AND UPPER(site_addr) LIKE :addr
                LIMIT 1
            """),
            {"town": town.title(), "addr": f"%{address.upper().split(',')[0][:20]}%"},
        ).fetchone()
        if addr_row:
            return addr_row[0]

    # Spatial proximity fallback
    row = session.execute(
        text("""
            SELECT loc_id FROM parcels
            WHERE ST_DWithin(
                geom,
                ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986),
                500
            )
            ORDER BY geom <-> ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986)
            LIMIT 1
        """),
        {"lat": lat, "lon": lon},
    ).fetchone()
    return row[0] if row else None


# ── Upsert ────────────────────────────────────────────────────────────────────

_UPSERT = text("""
    INSERT INTO precedents
        (town_id, docket, project_type, project_address, parcel_loc_id,
         applicant, decision, filing_date, decision_date,
         meeting_body, source_url, full_text, confidence, geom, created_at)
    VALUES (
        (SELECT town_id FROM municipalities WHERE town_name = :town LIMIT 1),
        :docket, :project_type, :address, :parcel_loc_id,
        :applicant, :decision, :filing_date, :decision_date,
        :meeting_body, :source_url, :full_text, :confidence,
        CASE WHEN :lat IS NOT NULL
             THEN ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 26986)
             ELSE NULL END,
        :now
    )
    ON CONFLICT (docket) WHERE docket IS NOT NULL DO UPDATE SET
        decision       = EXCLUDED.decision,
        decision_date  = EXCLUDED.decision_date,
        full_text      = COALESCE(EXCLUDED.full_text, precedents.full_text),
        parcel_loc_id  = COALESCE(EXCLUDED.parcel_loc_id, precedents.parcel_loc_id),
        source_url     = EXCLUDED.source_url
""")


def _infer_project_type(description: str) -> str:
    desc = description.lower()
    if re.search(r"bess|battery|energy storage", desc):
        return "bess_standalone"
    if re.search(r"solar|pv|photovoltaic", desc):
        return "solar_ground_mount"
    return "solar_ground_mount"  # default for WPA filings


def _parse_date(s: str) -> datetime | None:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def _process_result(
    session,
    row: dict,
    detail: dict,
    dry_run: bool,
) -> bool:
    description = detail.get("description") or row.get("description", "")
    full_text = detail.get("full_text", "")

    # Filter: only keep solar/BESS projects
    combined_text = f"{description} {full_text} {row.get('applicant', '')}"
    if not SOLAR_BESS_KEYWORDS.search(combined_text):
        return False

    activity_lower = row.get("activity", "").lower()
    decision = next(
        (v for k, v in ACTIVITY_DECISION_MAP.items() if k in activity_lower),
        None,
    )
    if not decision:
        return False

    meeting_body = next(
        (v for k, v in ACTIVITY_BODY_MAP.items() if k in activity_lower),
        "conservation_commission",
    )
    project_type = _infer_project_type(description)
    decision_date = _parse_date(row.get("status_date", ""))
    town = row.get("town", "").title()

    # Geocode
    lat, lon, parcel_loc_id = None, None, None
    address = row.get("address", "")
    if address and town:
        coords = _geocode(address, town)
        if coords:
            lat, lon = coords
            parcel_loc_id = _find_parcel(session, lat, lon, address, town)

    docket = row.get("dep_file") or None
    if dry_run:
        print(f"    [dry-run] {docket} | {town} | {decision} | {project_type} | parcel={parcel_loc_id}")
        return True

    session.execute(_UPSERT, {
        "town": town,
        "docket": docket,
        "project_type": project_type,
        "address": address,
        "parcel_loc_id": parcel_loc_id,
        "applicant": row.get("applicant", ""),
        "decision": decision,
        "filing_date": None,
        "decision_date": decision_date,
        "meeting_body": meeting_body,
        "source_url": row.get("detail_url"),
        "full_text": full_text[:8000] if full_text else None,
        "confidence": 0.85,
        "lat": lat,
        "lon": lon,
        "now": datetime.now(timezone.utc),
    })
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def run(
    towns: list[str],
    start_year: int = 2020,
    dry_run: bool = False,
) -> int:
    start_date = f"01/01/{start_year}"
    end_date = datetime.now().strftime("%m/%d/%Y")
    total = 0

    with httpx.Client(follow_redirects=True, timeout=30) as client:
        # Get town → dropdown value mapping once
        print("Fetching eDEP town list ...")
        try:
            town_options = _parse_town_options(client)
        except Exception as e:
            print(f"Cannot reach eDEP portal: {e}")
            print("The portal may require VPN or be temporarily unavailable.")
            return 0

        for town_name in towns:
            # Match our town name to eDEP's dropdown value
            key = town_name.upper()
            town_value = town_options.get(key) or town_options.get(f"TOWN OF {key}")
            if not town_value:
                # Fuzzy: try starts-with
                for opt_key, opt_val in town_options.items():
                    if opt_key.startswith(key):
                        town_value = opt_val
                        break

            if not town_value:
                print(f"  {town_name}: not found in eDEP dropdown — skipping")
                continue

            print(f"  Searching {town_name} ({start_date} → {end_date}) ...")
            try:
                rows = _search_town(client, town_value, start_date, end_date)
            except Exception as e:
                print(f"    Error: {e}")
                continue

            town_count = 0
            with SessionLocal() as session:
                for row in rows:
                    row["town"] = town_name  # normalize

                    # Fetch detail only if description looks relevant
                    detail: dict = {}
                    if row.get("detail_url"):
                        detail = _fetch_detail(client, row["detail_url"])

                    if _process_result(session, row, detail, dry_run):
                        town_count += 1

                if not dry_run:
                    session.commit()

            print(f"    → {town_count} solar/BESS decisions ingested")
            total += town_count

    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape MA DEP eDEP WPA decisions for solar/BESS")
    parser.add_argument("--town", help="Single town name")
    parser.add_argument("--all-towns", action="store_true", help="All towns in municipalities table")
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.all_towns:
        with SessionLocal() as session:
            towns = session.execute(
                text("SELECT town_name FROM municipalities ORDER BY town_name")
            ).scalars().all()
    elif args.town:
        towns = [args.town]
    else:
        parser.print_help()
        sys.exit(1)

    print(f"eDEP WPA scraper — {len(towns)} town(s), start_year={args.start_year}")
    n = run(towns, start_year=args.start_year, dry_run=args.dry_run)
    print(f"\nTotal: {n} precedents ingested")


if __name__ == "__main__":
    main()
