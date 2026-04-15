"""Generate example score-report JSON files for all benchmark parcels.

Output: examples/<parcel-id>.json  (relative to repo root)

Usage:
    python scripts/gen_examples.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

# Ensure app is importable when run from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.scoring.engine import score_site
from app.scoring.resolver import ResolveError, resolve_parcel

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_PATH = REPO_ROOT / "docs" / "benchmark.yaml"
EXAMPLES_DIR = REPO_ROOT / "examples"


def main() -> None:
    EXAMPLES_DIR.mkdir(exist_ok=True)
    spec = yaml.safe_load(BENCHMARK_PATH.read_text())

    with SessionLocal() as session:
        for p in spec["parcels"]:
            parcel_id_slug = p["id"]
            address = p["address"]
            project_type = p.get("project_type", "generic")

            print(f"  scoring {parcel_id_slug}...", end=" ", flush=True)
            try:
                loc_id, mode = resolve_parcel(session, address)
            except ResolveError as e:
                print(f"UNRESOLVED ({e})")
                continue

            report = score_site(
                session,
                parcel_id=loc_id,
                project_type=project_type,
            )

            out = {
                "id": parcel_id_slug,
                "address": address,
                "resolution_mode": mode,
                "parcel_loc_id": loc_id,
                "report": report.model_dump(mode="json"),
            }

            dest = EXAMPLES_DIR / f"{parcel_id_slug}.json"
            dest.write_text(json.dumps(out, indent=2))
            print(f"OK  score={report.total_score:.1f}  bucket={report.bucket}")

    print(f"\nWrote {len(list(EXAMPLES_DIR.glob('*.json')))} files to {EXAMPLES_DIR}")


if __name__ == "__main__":
    main()
