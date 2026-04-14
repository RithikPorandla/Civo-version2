"""Refine ESMP project geocodes for projects whose xlsx 'Primary
Municipality' was too coarse (whole-town centroid) to score accurately.

Each override here is sourced from the ESMP filing's own text (DPU 24-10
Permitting Notes / nearby-infrastructure callouts) and/or the benchmark
YAML's documented project locations. These are still approximations —
the projects are pending siting — but they drop the anchor onto the
real planned corridor rather than a random urban block of the primary
municipality.

Run this, then re-run ``ingest.esmp_projects`` to repopulate the DB.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ingest.esmp_projects import CACHE_PATH, PLACES_URL  # noqa: E402

# project_id (CSV "Project ID") -> more-specific Places query.
# Sourced from DPU 24-10 permitting notes and benchmark.yaml descriptions.
OVERRIDES: dict[str, str] = {
    # New Burlington Substation: "~2 acres Eversource-owned land off Winn St"
    # with ~2.5 mi new OH transmission through Wilmington into Woburn.
    "19": "Winn Street, Burlington, MA",
    # New Saxonville/Natick Substation: "near transmission ROW between
    # Saxonville #278 and Framingham Ring #240". Saxonville is a village
    # in Framingham, not Natick — the xlsx Municipality is misleading.
    "25": "Saxonville, Framingham, MA",
    # New North Acton Substation: long-term replacement for Maynard interim;
    # serves North Acton / Maynard / Sudbury / Carlisle. North Acton parcels
    # are the target area.
    "29": "North Acton, Acton, MA",
    # New Worthington Substation: rural WMA, ~200mi feeders currently.
    # Worthington town center is acceptable but bias toward the rural
    # substation service area (Chester Rd).
    "23": "Huntington Road, Worthington, MA",
    # New Falmouth Tap Substation: rebuild of existing #924 switching
    # station. DPU 24-10 cross-references Stephens Lane as the
    # station access road (see Project 6, 5th Submarine Cable note).
    "7": "Stephens Lane, Falmouth, MA",
    # East Freetown Group CIP: new Substation #690 replacing unfiled
    # New Bedford Group CIP; serves North New Bedford + East Freetown +
    # Dartmouth; project sits near Industrial Park #636 transfer load.
    "EFT": "East Freetown Industrial Park, East Freetown, MA",
    # 5th Submarine Cable: shore landing at Stephens Lane per ESMP text.
    "6": "Stephens Lane, Falmouth, MA",
    # Whately-Deerfield Group CIP: agricultural-commercial area;
    # Cumberland #22B is in Whately; anchor at the Whately/Deerfield
    # border where the CIP substation would relieve multiple subs.
    "WD-CIP": "Christian Lane, Whately, MA",
    # New South End Substation: Boston South End anchor.
    "27": "Washington Street, South End, Boston, MA",
    # New Dennis/Brewster Substation: Lower Cape capacity solution
    # covering Harwich/Dennis/Brewster/Chatham/Orleans.
    "31": "Route 6A, Dennis, MA",
    # New Waltham Substation: relieves North & West Waltham subs.
    "33": "Main Street, Waltham, MA",
}


def main() -> None:
    key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
    if not key:
        raise SystemExit("GOOGLE_PLACES_API_KEY required")

    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    with httpx.Client(timeout=30) as client:
        for pid, query in OVERRIDES.items():
            r = client.get(
                PLACES_URL,
                params={
                    "input": query,
                    "inputtype": "textquery",
                    "fields": "formatted_address,geometry,place_id,types",
                    "key": key,
                },
            )
            r.raise_for_status()
            data = r.json()
            if data.get("status") != "OK" or not data.get("candidates"):
                print(f"  [{pid}] {query!r} -> {data.get('status')} (kept old)")
                continue
            c = data["candidates"][0]
            old = cache.get(pid, {})
            cache[pid] = {
                "status": "OK",
                "place_id": c.get("place_id"),
                "formatted_address": c.get("formatted_address"),
                "types": c.get("types") or [],
                "lat": c["geometry"]["location"]["lat"],
                "lon": c["geometry"]["location"]["lng"],
                "query": query,
                "refined_from_query": old.get("query"),
            }
            print(
                f"  [{pid}] {query!r} -> "
                f"{c['geometry']['location']['lat']:.4f},{c['geometry']['location']['lng']:.4f} "
                f"({c.get('formatted_address')})"
            )
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))
    print(f"Wrote {CACHE_PATH}")


if __name__ == "__main__":
    main()
