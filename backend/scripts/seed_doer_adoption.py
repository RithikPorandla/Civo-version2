"""Seed initial DOER adoption rows for the 5 currently-modeled towns.

None of the 5 seeded towns (Acton, Cambridge, East Freetown, Whately,
Burlington) has a verified public record of adopting the DOER October
2025 model bylaw in this session, so we default every row to
``adoption_status='unknown'`` with ``confidence=0.3`` and
``source_type='manual_entry'``.

When a user confirms a town's actual status (from a town-meeting warrant,
AG Municipal Law approval, or town website), re-run this script with
overrides or update directly. The research agent will eventually own
this table automatically (step 7a — deferred).

Ground rule: unknown is always better than fabricated. See CIVO_BRAIN §9.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db import SessionLocal


DOER_VERSIONS = {
    "solar": "October 2025 Draft",
    "bess": "October 2025 Model Bylaw",
}

# Default seed: unknown adoption, low confidence, manual entry.
# Per the research plan, these flip to 'adopted' / 'in_progress' as we
# manually verify each town's warrant and AG-approval status.
TOWNS = [
    "Acton",
    "Cambridge",
    "East Freetown",
    "Whately",
    "Burlington",
]


def main() -> None:
    with SessionLocal() as session:
        written = 0
        for town_name in TOWNS:
            row = session.execute(
                text("SELECT town_id FROM municipalities WHERE town_name = :t"),
                {"t": town_name},
            ).first()
            if row is None:
                print(f"  !! municipality {town_name!r} not loaded; skipping")
                continue
            town_id = row[0]

            for project_type in ("solar", "bess"):
                session.execute(
                    text(
                        """
                        INSERT INTO municipal_doer_adoption (
                            state, municipality_id, project_type,
                            adoption_status, source_url, source_type,
                            confidence, doer_version_ref, extracted_at,
                            reviewed_by_human
                        ) VALUES (
                            'MA', :mid, :pt, 'unknown',
                            :src_url, 'manual_entry',
                            0.3, :ver, :now, false
                        )
                        ON CONFLICT (municipality_id, project_type) DO NOTHING
                        """
                    ),
                    {
                        "mid": town_id,
                        "pt": project_type,
                        "src_url": "https://www.mass.gov/regulations/225-CMR-29-225-cmr-2900-small-clean-energy-infrastructure-facility-siting-and-permitting-draft-regulation",  # noqa: E501
                        "ver": DOER_VERSIONS[project_type],
                        "now": datetime.now(timezone.utc),
                    },
                )
                written += 1
        session.commit()
        print(f"seeded {written} DOER adoption rows across {len(TOWNS)} towns")


if __name__ == "__main__":
    main()
