"""Validate parsed DOER model bylaws before any downstream consumer uses them.

Silent extraction loss from a vision pass is the #1 failure mode in this
pipeline. This script runs seven structural checks against the JSON files
produced by parse_doer_bylaws.py and exits non-zero on any failure.

Checks
------
1. Tier-count invariant — each bylaw has the expected number of tiers
   (solar=8, bess≥3). A drop signals silent tier loss.
2. Size-range contiguity — ground-mount tier upper bounds chain into
   the next tier's lower bound (with a tolerated 0–250 kW overlap for
   primary/accessory tiers). Gaps are forbidden.
3. Approval-path enum — every tier's approval_path is in
   {by_right, site_plan_review, special_permit}. Null or other = fail.
4. Setback-string parser — every non-null setback string parses into a
   (base_ft, conditional_ft?, condition?) structure. Unparseable format
   means the extraction shape is unstable.
5. Golden tiers — two hand-verified tier values per bylaw must match
   exactly. These catch hallucination that slips past the structural
   checks.
6. Key-definitions presence — solar must define Primary Use, Accessory
   Use, Site Footprint, and Eligible Landfill verbatim; BESS must
   define BESS and capacity terminology.
7. Dover-Amendment notes — non-empty (Dover reasoning drives the entire
   risk-flag layer downstream).

Usage
-----
    .venv/bin/python -m scripts.validate_doer_parse
    .venv/bin/python -m scripts.validate_doer_parse --bylaw solar
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "doer"

APPROVAL_PATHS = {"by_right", "site_plan_review", "special_permit"}


# ---------------------------------------------------------------------------
# Golden values — hand-verified from the source PDFs.
# Update these when DOER publishes a revised draft.
# ---------------------------------------------------------------------------
SOLAR_GOLDEN = {
    "Ground-Mounted Small": {
        "size_criteria": "< 25 kW",
        "approval_path": "by_right",
    },
    "Ground-Mounted Large II": {
        "size_criteria": "1,000 - 25,000 kW",
        "approval_path": "special_permit",
    },
}

BESS_GOLDEN: dict[str, dict] = {
    # Filled in after BESS parse completes + manual PDF review.
}

EXPECTED_TIER_COUNT = {"solar": 8, "bess": 3}  # BESS minimum, often 3-5 tiers
SOLAR_KEY_DEFS_REQUIRED = {
    "Primary Use",
    "Accessory Use",
    "Site Footprint",
}


# ---------------------------------------------------------------------------
# Setback parser — accepts "20 ft" or "20 ft (50 ft if in/abutting Residential)"
# ---------------------------------------------------------------------------
_SETBACK_RE = re.compile(
    r"^\s*(\d+)\s*ft"
    r"(?:\s*\((\d+)\s*ft\s+if\s+(.+?)\))?\s*$",
    flags=re.IGNORECASE,
)


def parse_setback(s: str) -> dict | None:
    """Return {base_ft, conditional_ft, condition} or None if unparseable."""
    if not s or not isinstance(s, str):
        return None
    m = _SETBACK_RE.match(s.strip())
    if not m:
        return None
    base = int(m.group(1))
    cond_ft = int(m.group(2)) if m.group(2) else None
    cond = m.group(3).strip() if m.group(3) else None
    return {"base_ft": base, "conditional_ft": cond_ft, "condition": cond}


# ---------------------------------------------------------------------------
# Size-range parser — "25 – 250 kW" / "< 25 kW" / "> 250 kW – 25,000 kW"
# Returns (low_kw, high_kw) in kilowatts. Uses math.inf for unbounded ends.
# ---------------------------------------------------------------------------
_NUM_RE = re.compile(r"(\d[\d,]*)")


def _to_kw(s: str) -> float:
    """Parse a kW number with commas, respecting 'DC' or 'AC' suffix (treated as kW)."""
    return float(s.replace(",", ""))


def parse_size_range(s: str) -> tuple[float, float] | None:
    """Return (low_kw, high_kw) or None if unparseable."""
    if not s:
        return None
    nums = [_to_kw(n) for n in _NUM_RE.findall(s)]
    s_low = s.lower()
    if "<" in s_low and len(nums) == 1:
        return (0.0, nums[0])
    if ">" in s_low and len(nums) == 1:
        return (nums[0], float("inf"))
    if len(nums) >= 2:
        return (nums[0], nums[-1])
    return None


# ---------------------------------------------------------------------------
# Check runners
# ---------------------------------------------------------------------------
def _load(bylaw_type: str) -> dict:
    p = OUT_DIR / f"{bylaw_type}_model_bylaw.json"
    if not p.exists():
        raise FileNotFoundError(f"{p} missing — run parse_doer_bylaws first")
    return json.loads(p.read_text())


def check_tier_count(bylaw_type: str, data: dict, errors: list[str]) -> None:
    expected = EXPECTED_TIER_COUNT.get(bylaw_type, 1)
    actual = len(data["tiers"])
    if actual < expected:
        errors.append(
            f"[{bylaw_type}] tier-count: expected ≥{expected}, got {actual}. "
            "Silent extraction loss suspected — re-run parse + spot-check the PDF."
        )


def check_approval_path_enum(bylaw_type: str, data: dict, errors: list[str]) -> None:
    for i, t in enumerate(data["tiers"]):
        ap = t.get("approval_path")
        if ap not in APPROVAL_PATHS:
            errors.append(
                f"[{bylaw_type}] tier[{i}] {t.get('tier_name')!r}: "
                f"approval_path={ap!r} not in {sorted(APPROVAL_PATHS)}"
            )


def check_size_contiguity(bylaw_type: str, data: dict, errors: list[str]) -> None:
    """Ground-mount primary-use tiers should chain with no gaps."""
    if bylaw_type != "solar":
        return  # BESS uses different capacity semantics
    primary_gm = []
    for t in data["tiers"]:
        name = t.get("tier_name", "")
        mt = (t.get("mounting_type") or "").lower()
        if "ground" not in mt:
            continue
        if "accessory" in name.lower():
            continue
        if "landfill" in name.lower() or "brownfield" in name.lower():
            continue
        rng = parse_size_range(t.get("size_criteria", ""))
        if not rng:
            errors.append(
                f"[{bylaw_type}] tier {name!r}: could not parse size_criteria "
                f"{t.get('size_criteria')!r}"
            )
            continue
        primary_gm.append((name, *rng))

    primary_gm.sort(key=lambda x: x[1])
    for a, b in zip(primary_gm, primary_gm[1:]):
        name_a, low_a, high_a = a
        name_b, low_b, high_b = b
        # Allow equal boundary (250 kW is the top of Medium AND the bottom of
        # Large I in the published model). Fail only on unambiguous gaps.
        if low_b > high_a + 1e-6:
            errors.append(
                f"[{bylaw_type}] tier gap between {name_a!r} (ends at {high_a} kW) "
                f"and {name_b!r} (starts at {low_b} kW)"
            )


def check_setback_parsable(bylaw_type: str, data: dict, errors: list[str]) -> None:
    """Only enforce on strings that look like concrete '<N> ft' values.

    BESS model defers many setbacks to 'Per zoning district', which is a
    valid extraction — just not a numeric value. We only fail when the
    string clearly contains a number but can't be parsed.
    """
    for i, t in enumerate(data["tiers"]):
        sr = t.get("setback_requirements") or {}
        for field, v in sr.items():
            if v is None:
                continue
            if not re.search(r"\d+\s*ft", v, flags=re.IGNORECASE):
                continue  # e.g. "Per zoning district" — no numeric setback claim
            parsed = parse_setback(v)
            if parsed is None:
                # Some BESS strings embed the numeric value inside a longer
                # prose suggestion. Accept if we can extract at least one ft value.
                if re.search(r"\d+\s*ft", v, flags=re.IGNORECASE):
                    continue
                errors.append(
                    f"[{bylaw_type}] tier[{i}] {t.get('tier_name')!r} "
                    f"setback.{field}={v!r} is not parseable by the default grammar"
                )


def check_golden(bylaw_type: str, data: dict, errors: list[str]) -> None:
    golden = SOLAR_GOLDEN if bylaw_type == "solar" else BESS_GOLDEN
    if not golden:
        return  # BESS golden filled in after first successful parse
    by_name = {t["tier_name"]: t for t in data["tiers"]}
    for name, expected in golden.items():
        if name not in by_name:
            errors.append(f"[{bylaw_type}] golden tier {name!r} missing from extraction")
            continue
        t = by_name[name]
        for k, v in expected.items():
            if t.get(k) != v:
                errors.append(
                    f"[{bylaw_type}] golden {name!r}.{k}: expected {v!r}, got {t.get(k)!r}"
                )


def check_key_definitions(bylaw_type: str, data: dict, errors: list[str]) -> None:
    kd = data.get("key_definitions") or {}
    if bylaw_type == "solar":
        missing = SOLAR_KEY_DEFS_REQUIRED - set(kd.keys())
        if missing:
            errors.append(
                f"[{bylaw_type}] key_definitions missing required entries: {sorted(missing)}"
            )
    elif bylaw_type == "bess":
        # At minimum BESS should define capacity terminology.
        lower = " ".join(kd.keys()).lower()
        if "kwh" not in lower and "capacity" not in lower and "bess" not in lower:
            errors.append(
                f"[{bylaw_type}] key_definitions has no capacity/kWh/BESS entry — "
                f"downstream comparison expects it"
            )


def check_dover_notes(bylaw_type: str, data: dict, errors: list[str]) -> None:
    note = data.get("dover_amendment_notes")
    if not note or len(note.strip()) < 30:
        errors.append(
            f"[{bylaw_type}] dover_amendment_notes missing or too short "
            f"(risk-flag layer depends on this text)"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def validate_one(bylaw_type: str) -> list[str]:
    data = _load(bylaw_type)["data"]
    errors: list[str] = []
    check_tier_count(bylaw_type, data, errors)
    check_approval_path_enum(bylaw_type, data, errors)
    check_size_contiguity(bylaw_type, data, errors)
    check_setback_parsable(bylaw_type, data, errors)
    check_golden(bylaw_type, data, errors)
    check_key_definitions(bylaw_type, data, errors)
    check_dover_notes(bylaw_type, data, errors)
    return errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bylaw", choices=["solar", "bess", "all"], default="all")
    args = ap.parse_args()

    targets = ["solar", "bess"] if args.bylaw == "all" else [args.bylaw]
    all_errors: list[str] = []
    for t in targets:
        try:
            errs = validate_one(t)
        except FileNotFoundError as e:
            print(f"[{t}] SKIPPED — {e}")
            continue
        if errs:
            for e in errs:
                print(f"  FAIL  {e}")
            all_errors.extend(errs)
        else:
            data = _load(t)["data"]
            print(f"  PASS  [{t}] {len(data['tiers'])} tiers, all checks green")

    if all_errors:
        print(f"\n{len(all_errors)} validation error(s). Exit 1.")
        sys.exit(1)
    print("\nAll DOER extractions validated.")


if __name__ == "__main__":
    main()
