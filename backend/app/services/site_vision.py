"""Claude-vision site characterization for a parcel.

Per the 2026-04-17 Chris meeting + CIVO_BRAIN §13 Phase C: run Claude
vision on an aerial tile covering the parcel and return structured
features — impervious %, canopy %, detected buildings, visible water,
a short narrative — alongside a confidence score. The output is
always reconciled against the authoritative MassGIS land-use layer:
if vision disagrees with the GIS, we surface the conflict rather than
silently trusting the model.

Image source
------------
Esri's World Imagery ``ExportImage`` endpoint is free, returns a PNG
directly for a given bbox + size, and covers MA at ~30 cm. We fetch
at 1024×1024 for a parcel's bbox + 30 % buffer so the model sees
surrounding context.

Caching
-------
One row per ``(parcel_loc_id, vision_version)`` in
``parcel_characterizations``. When the prompt or schema changes, bump
``VISION_VERSION`` and old rows are ignored — the next request
triggers a fresh extraction.
"""

from __future__ import annotations

import base64
import io
import json
import os
from typing import Any

import httpx
from anthropic import Anthropic, RateLimitError
from PIL import Image, ImageDraw
from pydantic import BaseModel, Field, ValidationError
from shapely import wkt as shapely_wkt
from shapely.geometry.base import BaseGeometry
from sqlalchemy import text
from sqlalchemy.orm import Session

# Bump whenever prompt, schema, or output structure changes. The cache
# keys on this so old rows are ignored after a bump.
VISION_VERSION = "v2-2026-04-20"
MODEL_ID = "claude-opus-4-7"

ESRI_EXPORT_URL = (
    "https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export"
)


# ---------------------------------------------------------------------------
# Output schema (what Claude is asked to produce + what the API returns)
# ---------------------------------------------------------------------------
class SurfaceBreakdown(BaseModel):
    surface: str
    pct: float = Field(..., ge=0.0, le=100.0)


class SiteCharacterization(BaseModel):
    """Structured AI view of a parcel — complementary to, never replacing,
    the authoritative GIS-derived constraint scoring."""

    impervious_pct: float = Field(..., ge=0.0, le=100.0)
    tree_canopy_pct: float = Field(..., ge=0.0, le=100.0)
    open_ground_pct: float = Field(..., ge=0.0, le=100.0, description="grass / bare soil / gravel")
    water_visible: bool
    water_description: str | None = Field(
        default=None,
        description="free text — e.g. 'stream along south edge', 'retention pond, 0.3 ac'",
    )
    detected_building_count: int = Field(..., ge=0)
    detected_paved_area_description: str | None = None
    surface_breakdown: list[SurfaceBreakdown] = Field(default_factory=list)
    narrative: str = Field(
        ...,
        description="2-3 sentences describing what the parcel looks like and "
        "what a developer would note on first pass",
    )
    site_characteristics: list[str] = Field(
        default_factory=list,
        description="short bullet-ready phrases — 'heavily wooded east half', "
        "'frontage on paved road', 'no visible wetlands'",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)


class SiteAnalysisResponse(BaseModel):
    parcel_loc_id: str
    vision_version: str
    model_id: str
    image_source: str
    image_bbox_wgs84: dict
    characterization: SiteCharacterization
    reconciliation: "Reconciliation | None" = None
    cached: bool = False


class Reconciliation(BaseModel):
    """How the vision output lines up with MassGIS land-use.

    When the two diverge meaningfully (>15 pct pts on impervious
    coverage), we flag it so the UI can show 'vision says 45%, MassGIS
    LU/LC says 62%' and let the expert decide.
    """

    massgis_developed_pct: float | None = None
    vision_impervious_pct: float
    delta: float | None = None
    flag: str | None = Field(
        default=None,
        description="null | 'aligned' | 'diverges' — set when delta > 15 pts",
    )
    note: str | None = None


SiteAnalysisResponse.model_rebuild()


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
PROMPT = """
You are characterizing a Massachusetts parcel for an energy-infrastructure
permitting platform. A permitting consultant is looking at this aerial image
to decide whether the site is a candidate for battery storage, ground-mount
solar, or substation development.

The red/yellow outline in the image is the parcel boundary. Everything OUTSIDE
the boundary is context — do NOT include it in your percentages or building
counts. Only describe what you can clearly see within the parcel.

Return ONLY a JSON object matching this schema. No markdown, no prose.

{
  "impervious_pct": 0-100 (paved surfaces + building footprints, inside parcel only),
  "tree_canopy_pct": 0-100 (closed or semi-closed canopy, inside parcel only),
  "open_ground_pct": 0-100 (grass, bare soil, gravel, inside parcel),
  "water_visible": true/false,
  "water_description": "short — e.g. 'small stream along SE edge', 'retention pond ~0.3 ac' or null",
  "detected_building_count": integer (clearly-visible structures inside parcel),
  "detected_paved_area_description": "e.g. 'large parking lot covers ~40% of parcel' or null",
  "surface_breakdown": [
    {"surface": "forest", "pct": 40},
    {"surface": "grass/lawn", "pct": 25},
    {"surface": "parking lot", "pct": 20},
    {"surface": "building roof", "pct": 10},
    {"surface": "other", "pct": 5}
  ],
  "narrative": "2-3 sentences — what a developer would note on first pass. Be concrete. Mention things like 'east half is heavily wooded', 'single building in NW corner', 'adjacent to highway'.",
  "site_characteristics": [
    "short phrases — one per obvious feature",
    "e.g. 'large tree-clearing required for ground-mount solar'",
    "e.g. 'flat, mostly open — good solar site'",
    "e.g. 'frontage on paved road for grid interconnection'"
  ],
  "confidence": 0.0-1.0 (lower when cloud cover, image quality issues, or unclear parcel boundary)
}

Rules:
- The three percentages (impervious, canopy, open_ground) should sum close to 100 (with small slack for water or features you can't classify).
- Do NOT fabricate features you can't clearly see. Set confidence lower if the image is ambiguous.
- Be honest about limitations — if the parcel extends off-frame, say so in the narrative.
- This output goes next to authoritative MassGIS data. Consultants will cross-check.
"""


# ---------------------------------------------------------------------------
# Image fetch — Esri World Imagery export
# ---------------------------------------------------------------------------
def _fetch_aerial_png(
    bbox_wgs84: tuple[float, float, float, float], size: int = 1024
) -> bytes:
    """Fetch an Esri World Imagery PNG for the given bbox (lon_w, lat_s, lon_e, lat_n).

    Esri's ExportImage returns a generic 500 for some combinations of narrow
    bboxes + large sizes. We try the requested size first and fall back through
    a smaller-size chain. png32 format avoids the palette-quantisation step
    that png8/png can introduce on complex aerial imagery.
    """
    lon_w, lat_s, lon_e, lat_n = bbox_wgs84

    sizes_to_try = [size]
    for fallback in (800, 512, 384):
        if fallback < size:
            sizes_to_try.append(fallback)

    last_error: Exception | None = None
    for s in sizes_to_try:
        params = {
            "bbox": f"{lon_w},{lat_s},{lon_e},{lat_n}",
            "bboxSR": "4326",
            "imageSR": "4326",
            "size": f"{s},{s}",
            "format": "png32",
            "transparent": "false",
            "f": "image",
        }
        try:
            r = httpx.get(ESRI_EXPORT_URL, params=params, timeout=60)
            # Success only if we actually got a PNG — Esri returns 500 as text/html
            # sometimes without raising, and other times as 200 text/html "Error: bytes".
            if (
                r.status_code == 200
                and r.content.startswith(b"\x89PNG")
            ):
                return r.content
            last_error = RuntimeError(
                f"Esri export at size={s} returned {r.status_code} "
                f"content-type={r.headers.get('content-type')}"
            )
        except httpx.HTTPError as e:
            last_error = e

    raise RuntimeError(
        f"Esri World Imagery export failed at every fallback size "
        f"({sizes_to_try}): {last_error}"
    )


def _parcel_geom_wgs84(
    session: Session, parcel_loc_id: str, buffer_pct: float = 0.18
) -> tuple[tuple[float, float, float, float], BaseGeometry]:
    """Return (bbox, parcel_geometry) both in WGS84.

    The bbox is the parcel's envelope expanded by ``buffer_pct`` in each
    direction — used for the Esri ExportImage request. The parcel geometry
    is used downstream to draw the boundary onto the fetched PNG so Claude
    knows exactly what it's analyzing.
    """
    row = (
        session.execute(
            text(
                """
                SELECT ST_AsText(ST_Transform(geom, 4326)) AS wkt,
                       ST_XMin(ST_Transform(geom, 4326)) AS lon_w,
                       ST_YMin(ST_Transform(geom, 4326)) AS lat_s,
                       ST_XMax(ST_Transform(geom, 4326)) AS lon_e,
                       ST_YMax(ST_Transform(geom, 4326)) AS lat_n
                FROM parcels WHERE loc_id = :pid
                """
            ),
            {"pid": parcel_loc_id},
        )
        .mappings()
        .first()
    )
    if not row:
        raise ValueError(f"parcel {parcel_loc_id!r} not found")
    w, s, e, n = row["lon_w"], row["lat_s"], row["lon_e"], row["lat_n"]
    lat_span = (n - s) * buffer_pct
    lon_span = (e - w) * buffer_pct
    bbox = (w - lon_span, s - lat_span, e + lon_span, n + lat_span)
    geom = shapely_wkt.loads(row["wkt"])
    return bbox, geom


def _draw_parcel_boundary(
    png_bytes: bytes,
    bbox_wgs84: tuple[float, float, float, float],
    parcel_geom: BaseGeometry,
) -> bytes:
    """Overlay the parcel boundary on the Esri PNG with a bright line.

    Vision models interpret the image far more accurately when they can see
    exactly which polygon is the subject — previous runs said "no parcel
    boundary is visible" and dropped confidence.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    width, height = img.size
    lon_w, lat_s, lon_e, lat_n = bbox_wgs84
    lon_span = lon_e - lon_w
    lat_span = lat_n - lat_s

    def to_px(lon: float, lat: float) -> tuple[float, float]:
        x = (lon - lon_w) / lon_span * width
        # PNG y-axis is top-to-bottom; geographic y is bottom-to-top.
        y = (lat_n - lat) / lat_span * height
        return (x, y)

    draw = ImageDraw.Draw(img, "RGBA")

    polys = []
    if parcel_geom.geom_type == "Polygon":
        polys = [parcel_geom]
    elif parcel_geom.geom_type == "MultiPolygon":
        polys = list(parcel_geom.geoms)

    for poly in polys:
        exterior = [to_px(lon, lat) for lon, lat in poly.exterior.coords]
        # Dark shadow + bright yellow + white inner line for max contrast on
        # any background — forest, pavement, or water.
        draw.line(exterior, fill=(0, 0, 0, 220), width=12)
        draw.line(exterior, fill=(255, 214, 10, 255), width=6)
        draw.line(exterior, fill=(255, 255, 255, 180), width=2)
        for interior in poly.interiors:
            ring = [to_px(lon, lat) for lon, lat in interior.coords]
            draw.line(ring, fill=(0, 0, 0, 220), width=10)
            draw.line(ring, fill=(255, 214, 10, 255), width=5)

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


# ---------------------------------------------------------------------------
# MassGIS reconciliation
# ---------------------------------------------------------------------------
# MassGIS 2016 Land Cover/Land Use covercode → broad category we use for
# "developed" comparison against vision impervious_pct. See
# https://www.mass.gov/info-details/massgis-data-2016-land-coverland-use
# for the full cover_code list.
_DEVELOPED_COVERCODES = {
    1,  # Developed Impervious - High Intensity
    2,  # Developed Impervious - Medium Intensity
    3,  # Developed Impervious - Low Intensity
    4,  # Developed Open - e.g. lawns, some impervious
}


def _reconcile_with_massgis(
    session: Session, parcel_loc_id: str, vision_impervious_pct: float
) -> Reconciliation:
    row = (
        session.execute(
            text(
                """
                WITH parcel AS (
                  SELECT geom FROM parcels WHERE loc_id = :pid
                ),
                overlap AS (
                  SELECT
                    lu.covercode,
                    SUM(ST_Area(ST_Intersection(lu.geom, parcel.geom))) AS ov_area
                  FROM land_use lu, parcel
                  WHERE ST_Intersects(lu.geom, parcel.geom)
                  GROUP BY lu.covercode
                ),
                total AS (
                  SELECT ST_Area(geom) AS a FROM parcel
                )
                SELECT
                  COALESCE(SUM(
                    CASE WHEN o.covercode IN (1,2,3) THEN o.ov_area ELSE 0 END
                  ) / NULLIF((SELECT a FROM total), 0) * 100, NULL) AS developed_pct
                FROM overlap o
                """
            ),
            {"pid": parcel_loc_id},
        )
        .mappings()
        .first()
    )
    developed = row["developed_pct"] if row else None
    if developed is None:
        return Reconciliation(
            vision_impervious_pct=vision_impervious_pct,
            note="MassGIS 2016 LU/LC has no coverage for this parcel — reconciliation skipped.",
        )
    delta = vision_impervious_pct - float(developed)
    flag = "diverges" if abs(delta) > 15 else "aligned"
    return Reconciliation(
        massgis_developed_pct=round(float(developed), 1),
        vision_impervious_pct=vision_impervious_pct,
        delta=round(delta, 1),
        flag=flag,
        note=None
        if flag == "aligned"
        else (
            f"Vision and MassGIS LU/LC disagree by {abs(round(delta, 1))} pts. "
            f"Vision is 2025-era imagery while MassGIS LU/LC is 2016 — updates to the "
            f"parcel since then (new roofs, lot clearing, pavement) can account for the gap."
        ),
    )


# ---------------------------------------------------------------------------
# Cache lookup
# ---------------------------------------------------------------------------
def _load_cached(
    session: Session, parcel_loc_id: str, vision_version: str
) -> dict | None:
    row = (
        session.execute(
            text(
                """
                SELECT characterization, image_source, image_bbox_wgs84, model_id
                FROM parcel_characterizations
                WHERE parcel_loc_id = :pid AND vision_version = :v
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"pid": parcel_loc_id, "v": vision_version},
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _persist(
    session: Session,
    parcel_loc_id: str,
    vision_version: str,
    model_id: str,
    image_source: str,
    bbox: tuple[float, float, float, float],
    image_len: int,
    characterization: SiteCharacterization,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO parcel_characterizations (
              parcel_loc_id, vision_version, model_id, image_source,
              image_bbox_wgs84, image_bytes, characterization, confidence
            ) VALUES (
              :pid, :v, :model, :src, CAST(:bbox AS jsonb),
              :len, CAST(:char AS jsonb), :conf
            )
            ON CONFLICT (parcel_loc_id, vision_version) DO UPDATE SET
              characterization = EXCLUDED.characterization,
              confidence = EXCLUDED.confidence,
              created_at = NOW()
            """
        ),
        {
            "pid": parcel_loc_id,
            "v": vision_version,
            "model": model_id,
            "src": image_source,
            "bbox": json.dumps(
                {"lon_w": bbox[0], "lat_s": bbox[1], "lon_e": bbox[2], "lat_n": bbox[3]}
            ),
            "len": image_len,
            "char": characterization.model_dump_json(),
            "conf": float(characterization.confidence),
        },
    )
    session.commit()


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------
def _call_claude_vision(png_bytes: bytes) -> SiteCharacterization:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = Anthropic()
    b64 = base64.standard_b64encode(png_bytes).decode("ascii")

    # Single-shot retry on rate limits.
    for _ in range(2):
        try:
            resp = client.messages.create(
                model=MODEL_ID,
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": PROMPT.strip()},
                        ],
                    }
                ],
            )
            break
        except RateLimitError:
            continue
    else:
        raise RuntimeError("rate-limited twice on site-vision call")

    text_parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    raw = "".join(text_parts).strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
        raw = raw.rsplit("```", 1)[0].strip()

    data = json.loads(raw)
    try:
        return SiteCharacterization(**data)
    except ValidationError as e:
        raise RuntimeError(f"vision output failed schema validation: {e}") from e


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def analyze_site(
    session: Session, parcel_loc_id: str, force: bool = False
) -> SiteAnalysisResponse:
    # Check cache first unless force-refresh.
    if not force:
        cached = _load_cached(session, parcel_loc_id, VISION_VERSION)
        if cached:
            char = SiteCharacterization(**cached["characterization"])
            reconciliation = _reconcile_with_massgis(
                session, parcel_loc_id, char.impervious_pct
            )
            return SiteAnalysisResponse(
                parcel_loc_id=parcel_loc_id,
                vision_version=VISION_VERSION,
                model_id=cached["model_id"],
                image_source=cached["image_source"],
                image_bbox_wgs84=cached["image_bbox_wgs84"],
                characterization=char,
                reconciliation=reconciliation,
                cached=True,
            )

    bbox, parcel_geom = _parcel_geom_wgs84(session, parcel_loc_id)
    raw_png = _fetch_aerial_png(bbox)
    png = _draw_parcel_boundary(raw_png, bbox, parcel_geom)
    char = _call_claude_vision(png)
    _persist(
        session,
        parcel_loc_id,
        VISION_VERSION,
        MODEL_ID,
        "esri-world-imagery",
        bbox,
        len(png),
        char,
    )
    reconciliation = _reconcile_with_massgis(
        session, parcel_loc_id, char.impervious_pct
    )
    return SiteAnalysisResponse(
        parcel_loc_id=parcel_loc_id,
        vision_version=VISION_VERSION,
        model_id=MODEL_ID,
        image_source="esri-world-imagery",
        image_bbox_wgs84={
            "lon_w": bbox[0],
            "lat_s": bbox[1],
            "lon_e": bbox[2],
            "lat_n": bbox[3],
        },
        characterization=char,
        reconciliation=reconciliation,
        cached=False,
    )
