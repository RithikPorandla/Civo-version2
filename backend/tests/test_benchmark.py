"""Benchmark test: runs the full scoring engine against docs/benchmark.yaml.

Fails if either (a) any parcel is more than 20 points off from its
``expected_score`` or (b) Pearson r across all parcels drops below 0.7.
Prints a per-parcel diff table regardless so regressions are easy to
diagnose.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import pytest
import yaml

from app.db import SessionLocal
from app.scoring.engine import score_site
from app.scoring.resolver import ResolveError, resolve_parcel

BENCHMARK_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "benchmark.yaml"
)
PER_PARCEL_TOLERANCE = 20.0
MIN_PEARSON = 0.7


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


@pytest.mark.skipif(
    os.getenv("CIVO_SKIP_BENCHMARK") == "1",
    reason="set CIVO_SKIP_BENCHMARK=1 to skip the full-DB benchmark",
)
def test_benchmark_matches_expected_scores():
    spec = yaml.safe_load(BENCHMARK_PATH.read_text())
    rows: list[dict] = []
    with SessionLocal() as session:
        for p in spec["parcels"]:
            try:
                loc_id, mode = resolve_parcel(session, p["address"])
            except ResolveError as e:
                rows.append(
                    {
                        "id": p["id"],
                        "address": p["address"],
                        "expected": p["expected_score"],
                        "computed": None,
                        "bucket": None,
                        "mode": f"unresolved: {e}",
                        "primary": None,
                    }
                )
                continue
            report = score_site(
                session,
                parcel_id=loc_id,
                project_type=p.get("project_type", "generic"),
            )
            rows.append(
                {
                    "id": p["id"],
                    "address": p["address"],
                    "expected": p["expected_score"],
                    "computed": report.total_score,
                    "bucket": report.bucket,
                    "mode": mode,
                    "primary": report.primary_constraint,
                    "flags": ",".join(report.ineligible_flags),
                }
            )

    # -- Print diff table ---------------------------------------------------
    print()
    print(
        f"{'id':32}  {'exp':>4}  {'calc':>5}  {'Δ':>5}  {'mode':9}  "
        f"{'primary':18}  bucket"
    )
    print("-" * 110)
    for r in rows:
        if r["computed"] is None:
            print(f"{r['id'][:32]:32}  {r['expected']:>4}  ---    ---    ---        ---                 ({r['mode']})")
            continue
        delta = r["computed"] - r["expected"]
        print(
            f"{r['id'][:32]:32}  {r['expected']:>4}  {r['computed']:>5.1f}  "
            f"{delta:+5.1f}  {r['mode']:9}  {(r['primary'] or ''):18}  {r['bucket']}"
        )

    # -- Assertions ---------------------------------------------------------
    scored = [r for r in rows if r["computed"] is not None]
    assert scored, "no parcels resolved"
    xs = [r["computed"] for r in scored]
    ys = [r["expected"] for r in scored]
    r_corr = _pearson(xs, ys)
    print(f"\nPearson r = {r_corr:.3f}  (threshold {MIN_PEARSON})")

    worst = max(scored, key=lambda r: abs(r["computed"] - r["expected"]))
    worst_delta = worst["computed"] - worst["expected"]
    print(
        f"worst: {worst['id']}  expected={worst['expected']}  "
        f"computed={worst['computed']}  Δ={worst_delta:+.1f}"
    )

    assert r_corr >= MIN_PEARSON, f"Pearson r {r_corr:.3f} below {MIN_PEARSON}"
    assert abs(worst_delta) <= PER_PARCEL_TOLERANCE, (
        f"{worst['id']} is {worst_delta:+.1f} off, exceeds ±{PER_PARCEL_TOLERANCE}"
    )
