"""Link-rot auditor for every gov citation URL Civo emits.

MassGIS / mass.gov restructures slugs roughly quarterly with no HTTP
redirects. This script is what we run before a demo, before a new
partner conversation, or on a schedule — whatever catches rot first.

For every URL collected from the codebase *and* from
``score_history.report`` citations already persisted in Postgres, we:

  1. HEAD-check (with a GET fallback for sites that don't serve HEAD).
  2. On 4xx / 5xx, ask the Wayback Machine
     (``http://archive.org/wayback/available``) for the latest snapshot.
  3. Print a patch-ready report: current URL, status code, suggested
     Wayback URL, and source file/line where it appears (best-effort).

The script never writes anywhere on its own. Human approval of each
replacement keeps citations honest.

Usage
-----
    .venv/bin/python -m scripts.check_citation_links
    .venv/bin/python -m scripts.check_citation_links --json out/linkcheck.json
    .venv/bin/python -m scripts.check_citation_links --only broken
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from app.db import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]

URL_RE = re.compile(r'https?://[^\s"\'\),]+')

# Only audit URLs pointing at authoritative sources. Town websites rot too,
# but they're harder to repair automatically; we treat those separately.
GOV_DOMAINS = (
    "mass.gov",
    "malegislature.gov",
    "arcgis.com",
    "arcgisserver.digital.mass.gov",
    "gis.data.mass.gov",
    "services1.arcgis.com",
    "mass-eoeea.maps.arcgis.com",
    "nfpa.org",
    "epa.gov",
    "fema.gov",
    "noaa.gov",
    "usda.gov",
)

USER_AGENT = "CivoLinkChecker/0.1 (+civo.energy)"
HTTP_TIMEOUT = 15.0


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class UrlRef:
    url: str
    source: str  # e.g. "backend/app/scoring/engine.py:42" or "db/score_history#report_id=12"

    def sort_key(self) -> tuple:
        return (self.url, self.source)


def _is_gov(url: str) -> bool:
    return any(d in url for d in GOV_DOMAINS)


def collect_from_source() -> list[UrlRef]:
    """Walk every .py / .ts / .tsx / .json under the repo for gov URLs."""
    out: list[UrlRef] = []
    patterns = [
        ("*.py", BACKEND_ROOT),
        ("*.ts", REPO_ROOT / "v2" / "frontend" / "src"),
        ("*.tsx", REPO_ROOT / "v2" / "frontend" / "src"),
        ("*.json", REPO_ROOT / "v2" / "data" / "processed" / "doer"),
    ]
    for glob, root in patterns:
        if not root.exists():
            continue
        for p in root.rglob(glob):
            if ".venv" in p.parts or "node_modules" in p.parts:
                continue
            try:
                txt = p.read_text(errors="ignore")
            except Exception:
                continue
            for m in URL_RE.finditer(txt):
                raw = m.group(0).rstrip(".,;]}")
                if not _is_gov(raw):
                    continue
                line = txt.count("\n", 0, m.start()) + 1
                rel = p.relative_to(REPO_ROOT)
                out.append(UrlRef(raw, f"{rel}:{line}"))
    return out


def collect_from_score_history(limit: int = 500) -> list[UrlRef]:
    """Scrape URLs out of persisted SuitabilityReport JSONB blobs.

    Reports already rendered to users carry the URL at time of scoring —
    older reports may have URLs that the current source no longer emits.
    """
    out: list[UrlRef] = []
    with SessionLocal() as session:
        rows = (
            session.execute(
                text(
                    """
                    SELECT id, report
                    FROM score_history
                    ORDER BY computed_at DESC
                    LIMIT :lim
                    """
                ),
                {"lim": limit},
            )
            .mappings()
            .all()
        )
    for r in rows:
        for m in URL_RE.finditer(json.dumps(r["report"])):
            raw = m.group(0).rstrip(".,;]}")
            if _is_gov(raw):
                out.append(UrlRef(raw, f"score_history#report_id={r['id']}"))
    return out


def dedupe(refs: Iterable[UrlRef]) -> dict[str, list[str]]:
    bucket: dict[str, list[str]] = {}
    for r in refs:
        bucket.setdefault(r.url, []).append(r.source)
    return bucket


# ---------------------------------------------------------------------------
# HEAD-check + Wayback fallback
# ---------------------------------------------------------------------------
def _probe(client: httpx.Client, url: str) -> tuple[int, str]:
    """Return (status_code, final_url) after following redirects.

    HEAD first; fall back to GET if the server rejects HEAD (some ESRI
    services return 405 on HEAD).
    """
    try:
        r = client.head(url, follow_redirects=True, timeout=HTTP_TIMEOUT)
        if r.status_code in (405, 403):
            r = client.get(url, follow_redirects=True, timeout=HTTP_TIMEOUT)
    except httpx.HTTPError as e:
        return (0, f"error:{type(e).__name__}:{e}")
    return (r.status_code, str(r.url))


def _wayback(client: httpx.Client, url: str) -> str | None:
    """Return the latest available Wayback Machine snapshot URL, or None."""
    try:
        r = client.get(
            "http://archive.org/wayback/available",
            params={"url": url},
            timeout=HTTP_TIMEOUT,
        )
        if not r.is_success:
            return None
        data = r.json()
        snap = (data.get("archived_snapshots") or {}).get("closest") or {}
        if snap.get("available") and snap.get("url"):
            return snap["url"]
    except (httpx.HTTPError, json.JSONDecodeError):
        pass
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--json",
        type=Path,
        help="Write the full audit to this JSON path (for CI / downstream).",
    )
    ap.add_argument(
        "--only",
        choices=["all", "broken"],
        default="all",
        help="Print every URL, or only the broken ones.",
    )
    ap.add_argument(
        "--skip-db",
        action="store_true",
        help="Skip the score_history pull (useful when DB is offline).",
    )
    args = ap.parse_args()

    refs: list[UrlRef] = collect_from_source()
    if not args.skip_db:
        try:
            refs.extend(collect_from_score_history())
        except Exception as e:  # pragma: no cover — DB may be down mid-demo
            print(f"[warn] couldn't read score_history: {e}")
    buckets = dedupe(refs)

    print(f"[check] {len(buckets)} distinct gov URLs across the codebase + DB")

    results: list[dict] = []
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        for url in sorted(buckets.keys()):
            status, final = _probe(client, url)
            healthy = 200 <= status < 400
            wayback = None if healthy else _wayback(client, url)
            results.append(
                {
                    "url": url,
                    "status": status,
                    "final_url": final,
                    "healthy": healthy,
                    "wayback_url": wayback,
                    "sources": buckets[url],
                }
            )

    broken = [r for r in results if not r["healthy"]]
    repairable = [r for r in broken if r["wayback_url"]]
    unfixable = [r for r in broken if not r["wayback_url"]]

    for r in results:
        if args.only == "broken" and r["healthy"]:
            continue
        badge = "OK  " if r["healthy"] else f"{r['status']:<4}"
        print(f"  {badge} {r['url']}")
        if not r["healthy"]:
            if r["wayback_url"]:
                print(f"       ↳ wayback: {r['wayback_url']}")
            else:
                print(f"       ↳ no wayback snapshot found — manual repair needed")
            for src in r["sources"][:3]:
                print(f"         used in: {src}")
            if len(r["sources"]) > 3:
                print(f"         …and {len(r['sources']) - 3} more")

    print(
        f"\n{len(results)} checked · "
        f"{len(results) - len(broken)} healthy · "
        f"{len(repairable)} repairable via Wayback · "
        f"{len(unfixable)} need manual replacement"
    )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "results": results,
                },
                indent=2,
            )
        )
        print(f"\nfull audit → {args.json}")

    # Non-zero exit when there are unfixable breaks so CI can fail fast.
    if unfixable:
        sys.exit(2)


if __name__ == "__main__":
    main()
