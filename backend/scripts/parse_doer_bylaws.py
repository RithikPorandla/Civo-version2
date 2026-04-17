"""Parse the DOER draft model bylaws (Solar + BESS) into structured JSON.

Input:  data/raw/regulatory/doer/2025-10_doer_{solar,bess}_model_bylaw.pdf
Output: data/processed/doer/{solar,bess}_model_bylaw.json

Uses Claude Opus 4.6 vision on the PDFs. Each extraction:
  - Is validated against the DOERModelBylaw pydantic schema.
  - Includes the source_pdf_hash so the seed migration can verify provenance.

Re-run whenever DOER publishes a new draft. The seeding migration picks
up whatever is currently on disk.

Usage:
  python -m scripts.parse_doer_bylaws
  python -m scripts.parse_doer_bylaws --bylaw solar
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MODEL = "claude-opus-4-7"

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "regulatory" / "doer"
OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "doer"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BYLAWS = {
    "solar": {
        "pdf": RAW_DIR / "2025-10_doer_solar_model_bylaw.pdf",
        "out": OUT_DIR / "solar_model_bylaw.json",
        "url": "https://www.mass.gov/doc/doer-draft-solar-model-bylaw/download",
    },
    "bess": {
        "pdf": RAW_DIR / "2025-10_doer_bess_model_bylaw.pdf",
        "out": OUT_DIR / "bess_model_bylaw.json",
        "url": "https://www.mass.gov/doc/doer-draft-battery-energy-storage-systems-bess-model-bylaw/download",
    },
}


# ---------------------------------------------------------------------------
# Pydantic schema — mirrors the doer_model_bylaws.parsed_data JSONB shape.
# ---------------------------------------------------------------------------
class SetbackRequirements(BaseModel):
    front: str | None = None
    side: str | None = None
    rear: str | None = None
    from_residential: str | None = None
    from_wetland: str | None = None


class TimelineRequirements(BaseModel):
    application_review_days: int | None = None
    public_hearing_required: bool | None = None
    consolidated_permit_deadline_months: int | None = None


class DOERTier(BaseModel):
    tier_name: str
    size_criteria: str
    mounting_type: str | None = None
    approval_path: str = Field(..., description="by_right | site_plan_review | special_permit")
    setback_requirements: SetbackRequirements = Field(default_factory=SetbackRequirements)
    height_limit: str | None = None
    screening_required: bool | None = None
    decommissioning_required: bool | None = None


class DOERModelBylaw(BaseModel):
    type: str  # 'solar' | 'bess'
    version: str
    effective_date: str | None = None
    tiers: list[DOERTier]
    fee_structure: str | None = None
    timeline_requirements: TimelineRequirements = Field(default_factory=TimelineRequirements)
    decommissioning_standards: str | None = None
    environmental_standards: list[str] = Field(default_factory=list)
    key_definitions: dict = Field(default_factory=dict)
    dover_amendment_notes: str | None = None


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
def _prompt_for(bylaw_type: str) -> str:
    return f"""
You are extracting the DOER draft model bylaw for **{bylaw_type.upper()}** into structured JSON.

Return ONLY a JSON object matching this exact schema. Nothing before or after.
Use null when a field is genuinely absent from the document — never guess.

{{
  "type": "{bylaw_type}",
  "version": "e.g. October 2025 Draft",
  "effective_date": "ISO date or free text if draft",
  "tiers": [
    {{
      "tier_name": "Tier 1 / Tier 2 / ...",
      "size_criteria": "e.g. ≤25 kW AC, 25 kW to 5 MW AC",
      "mounting_type": "rooftop | ground-mount | canopy | null (for BESS)",
      "approval_path": "by_right | site_plan_review | special_permit",
      "setback_requirements": {{
        "front": "...", "side": "...", "rear": "...",
        "from_residential": "...", "from_wetland": "..."
      }},
      "height_limit": "e.g. 20 ft",
      "screening_required": true/false,
      "decommissioning_required": true/false
    }}
  ],
  "fee_structure": "free text description",
  "timeline_requirements": {{
    "application_review_days": number or null,
    "public_hearing_required": true/false,
    "consolidated_permit_deadline_months": 12 (per 225 CMR 29.00)
  }},
  "decommissioning_standards": "free text summary",
  "environmental_standards": ["NFPA 855", "ANSI ...", ...],
  "key_definitions": {{"defined term": "definition"}},
  "dover_amendment_notes": "notes about M.G.L. c. 40A, § 3 interaction"
}}

IMPORTANT:
- `approval_path` must be exactly one of: by_right, site_plan_review, special_permit
- For BESS, `mounting_type` should be null.
- Extract EVERY tier in the document, including edge cases like "accessory" / "small-scale".
- If the bylaw references 225 CMR 29.00 for consolidated permitting, note 12 months.
- `key_definitions` should include the critical definitions used to classify projects (e.g. nameplate capacity, accessory use, commercial-scale).
- Return strict JSON only. No prose, no markdown fences.
""".strip()


# ---------------------------------------------------------------------------
# Vision call
# ---------------------------------------------------------------------------
def extract_one(bylaw_type: str) -> DOERModelBylaw:
    spec = BYLAWS[bylaw_type]
    pdf_path = spec["pdf"]
    if not pdf_path.exists():
        raise FileNotFoundError(f"{pdf_path} missing — run the download step first")

    pdf_bytes = pdf_path.read_bytes()
    b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")

    client = Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": _prompt_for(bylaw_type)},
                ],
            }
        ],
    )

    text_parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    raw = "".join(text_parts).strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        dump = OUT_DIR / f"{bylaw_type}_raw.txt"
        dump.write_text(raw)
        raise RuntimeError(
            f"Claude returned non-JSON. Raw output at {dump}. Error: {e}"
        ) from e

    try:
        model = DOERModelBylaw(**data)
    except ValidationError as e:
        dump = OUT_DIR / f"{bylaw_type}_invalid.json"
        dump.write_text(json.dumps(data, indent=2))
        raise RuntimeError(
            f"Parsed JSON failed schema validation. Saved at {dump}. Errors: {e}"
        ) from e

    return model


def write_output(bylaw_type: str, model: DOERModelBylaw) -> Path:
    spec = BYLAWS[bylaw_type]
    pdf_hash = hashlib.sha256(spec["pdf"].read_bytes()).hexdigest()
    payload = {
        "source": {
            "url": spec["url"],
            "pdf_path": str(spec["pdf"].relative_to(Path(__file__).resolve().parents[2])),
            "sha256": pdf_hash,
            "extracted_with": MODEL,
        },
        "data": model.model_dump(),
    }
    spec["out"].write_text(json.dumps(payload, indent=2))
    return spec["out"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bylaw", choices=["solar", "bess", "all"], default="all")
    args = ap.parse_args()

    targets = ["solar", "bess"] if args.bylaw == "all" else [args.bylaw]
    for t in targets:
        print(f"[parse] {t}: extracting…")
        model = extract_one(t)
        out = write_output(t, model)
        print(f"[parse] {t}: {len(model.tiers)} tiers → {out}")


if __name__ == "__main__":
    main()
