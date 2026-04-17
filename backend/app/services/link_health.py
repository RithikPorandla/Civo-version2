"""Runtime link-health cache for citation URLs.

Public API
----------
    check_urls(session, urls)
        Returns {url: LinkHealth} for every URL, hitting the cache
        first and falling back to a live HEAD probe. Cached rows are
        considered fresh for :data:`FRESH_TTL_S` seconds.

    enrich_citations_in_place(session, report_dict)
        Walks a serialized SuitabilityReport dict and mutates every
        citation to include a ``health`` field. Mutates in place so
        /report/{id} can pass straight through after the mutation.

Design
------
- The link_health table is an UPSERT cache. Rows never expire; a stale
  row just gets re-probed.
- HEAD is tried first; on 403/405 we fall back to GET (some ArcGIS
  endpoints reject HEAD).
- For any URL that returns a 4xx/5xx, we query the Wayback Machine
  ``available`` API and persist the closest archived snapshot so the
  frontend can offer a fallback link.
- Every probe runs in a short-timeout thread pool so a single slow
  endpoint can't hold up report rendering. Worst case we cache the
  "error" state and retry on the next call.
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

FRESH_TTL_S = 24 * 3600  # cached rows fresh for 24h
HTTP_TIMEOUT = 8.0
USER_AGENT = "CivoLinkChecker/0.1 (+civo.energy)"
MAX_WORKERS = 8


@dataclass
class LinkHealth:
    url: str
    healthy: bool
    status_code: int | None = None
    wayback_url: str | None = None
    final_url: str | None = None
    checked_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "healthy": self.healthy,
            "status_code": self.status_code,
            "wayback_url": self.wayback_url,
            "final_url": self.final_url,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
        }


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------
def _probe_one(client: httpx.Client, url: str) -> tuple[int, str]:
    try:
        r = client.head(url, follow_redirects=True, timeout=HTTP_TIMEOUT)
        if r.status_code in (403, 405):
            r = client.get(url, follow_redirects=True, timeout=HTTP_TIMEOUT)
        return r.status_code, str(r.url)
    except httpx.HTTPError:
        return 0, url


def _wayback(client: httpx.Client, url: str) -> str | None:
    try:
        r = client.get(
            "http://archive.org/wayback/available",
            params={"url": url},
            timeout=HTTP_TIMEOUT,
        )
        if not r.is_success:
            return None
        snap = (r.json().get("archived_snapshots") or {}).get("closest") or {}
        return snap["url"] if snap.get("available") and snap.get("url") else None
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError):
        return None


def _fresh_probe(url: str) -> LinkHealth:
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        code, final = _probe_one(client, url)
        healthy = 200 <= code < 400
        wb = None if healthy else _wayback(client, url)
    return LinkHealth(
        url=url,
        healthy=healthy,
        status_code=code or None,
        final_url=final,
        wayback_url=wb,
        checked_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# DB cache
# ---------------------------------------------------------------------------
def _load_cached(session: Session, urls: Iterable[str]) -> dict[str, LinkHealth]:
    url_list = list(urls)
    if not url_list:
        return {}
    rows = (
        session.execute(
            text(
                """
                SELECT url, status_code, healthy, wayback_url, final_url, checked_at
                FROM link_health
                WHERE url = ANY(:urls)
                """
            ),
            {"urls": url_list},
        )
        .mappings()
        .all()
    )
    out: dict[str, LinkHealth] = {}
    for r in rows:
        out[r["url"]] = LinkHealth(
            url=r["url"],
            healthy=bool(r["healthy"]),
            status_code=r["status_code"],
            wayback_url=r["wayback_url"],
            final_url=r["final_url"],
            checked_at=r["checked_at"],
        )
    return out


def _persist(session: Session, rows: Iterable[LinkHealth]) -> None:
    for h in rows:
        session.execute(
            text(
                """
                INSERT INTO link_health
                    (url, status_code, healthy, final_url, wayback_url, checked_at,
                     consecutive_failures)
                VALUES
                    (:url, :status_code, :healthy, :final_url, :wayback_url, :checked_at,
                     CASE WHEN :healthy THEN 0 ELSE 1 END)
                ON CONFLICT (url) DO UPDATE SET
                    status_code = EXCLUDED.status_code,
                    healthy = EXCLUDED.healthy,
                    final_url = EXCLUDED.final_url,
                    wayback_url = EXCLUDED.wayback_url,
                    checked_at = EXCLUDED.checked_at,
                    consecutive_failures = CASE
                        WHEN EXCLUDED.healthy THEN 0
                        ELSE link_health.consecutive_failures + 1
                    END
                """
            ),
            {
                "url": h.url,
                "status_code": h.status_code,
                "healthy": h.healthy,
                "final_url": h.final_url,
                "wayback_url": h.wayback_url,
                "checked_at": h.checked_at,
            },
        )
    session.commit()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def check_urls(session: Session, urls: Iterable[str]) -> dict[str, LinkHealth]:
    """Return a {url: LinkHealth} for every URL. Fresh rows served from cache."""
    url_set = {u for u in urls if u}
    if not url_set:
        return {}

    cached = _load_cached(session, url_set)
    now = datetime.now(timezone.utc)

    stale_urls: list[str] = []
    out: dict[str, LinkHealth] = {}
    for u in url_set:
        c = cached.get(u)
        if c and c.checked_at and (now - c.checked_at).total_seconds() < FRESH_TTL_S:
            out[u] = c
        else:
            stale_urls.append(u)

    if stale_urls:
        with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            results = list(ex.map(_fresh_probe, stale_urls))
        for h in results:
            out[h.url] = h
        _persist(session, results)

    return out


def enrich_citations_in_place(session: Session, report: dict[str, Any]) -> None:
    """Walk a serialized SuitabilityReport dict and attach health to each citation.

    A citation is any dict with a ``url`` key under
    ``criteria[*].citations[*]`` or ``citations[*]``. We attach a
    ``health`` dict with: ``{status: 'healthy'|'broken', wayback_url,
    status_code, checked_at}``. Frontend reads ``health.status`` to
    decide how to render.
    """
    urls: set[str] = set()

    def _walk_citations(cits: Any) -> list[dict]:
        return [c for c in (cits or []) if isinstance(c, dict) and c.get("url")]

    for cit in _walk_citations(report.get("citations")):
        urls.add(cit["url"])
    for crit in report.get("criteria") or []:
        for cit in _walk_citations(crit.get("citations")):
            urls.add(cit["url"])

    if not urls:
        return

    health = check_urls(session, urls)

    def _attach(cits: Any) -> None:
        for c in _walk_citations(cits):
            h = health.get(c["url"])
            if not h:
                continue
            c["health"] = {
                "status": "healthy" if h.healthy else "broken",
                "status_code": h.status_code,
                "wayback_url": h.wayback_url,
                "final_url": h.final_url,
                "checked_at": h.checked_at.isoformat() if h.checked_at else None,
            }

    _attach(report.get("citations"))
    for crit in report.get("criteria") or []:
        _attach(crit.get("citations"))
