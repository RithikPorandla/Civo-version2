"""Generate a 4-page consultant-ready PDF from a SuitabilityReport.

Requires reportlab (pure-Python, no system deps):
    pip install reportlab

Output structure:
    Page 1 — Cover: address, headline score, bucket, acreage, lat/lon, map tile
    Page 2 — Criterion breakdown: 7 criteria with scores and findings
    Page 3 — Constraints + Jurisdiction: constraint flags, DOER status, risk multiplier
    Page 4 — Precedents + next steps (from precedents table for the town)
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Brand palette (Earth & Paper)
_ACCENT = colors.HexColor("#5A3A1F")
_SAGE = colors.HexColor("#6B8F71")
_GOLD = colors.HexColor("#C9A84C")
_RUST = colors.HexColor("#B85C38")
_BG_LIGHT = colors.HexColor("#FAF7F2")
_TEXT_DIM = colors.HexColor("#6B6560")
_BORDER = colors.HexColor("#E2DDD8")

BUCKET_COLORS = {
    "SUITABLE": _SAGE,
    "CONDITIONALLY SUITABLE": _GOLD,
    "CONSTRAINED": _RUST,
}

STATIC_MAP_URL = (
    "https://staticmap.openstreetmap.de/staticmap.php"
    "?center={lat},{lon}&zoom=14&size=480x240&maptype=mapnik"
    "&markers={lat},{lon},red-pushpin"
)

styles = getSampleStyleSheet()

_h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=22, textColor=_ACCENT,
                     spaceAfter=4, fontName="Helvetica-Bold")
_h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, textColor=_ACCENT,
                     spaceBefore=12, spaceAfter=4, fontName="Helvetica-Bold")
_body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=13,
                       textColor=colors.HexColor("#2C2825"))
_dim = ParagraphStyle("Dim", parent=_body, textColor=_TEXT_DIM, fontSize=8)
_label = ParagraphStyle("Label", parent=_body, fontSize=7, fontName="Helvetica-Bold",
                        textColor=_TEXT_DIM, spaceAfter=1)
_finding = ParagraphStyle("Finding", parent=_body, fontSize=8, leading=12, textColor=_TEXT_DIM)
_score_large = ParagraphStyle("ScoreLarge", parent=styles["Normal"], fontSize=48,
                               fontName="Helvetica-Bold", alignment=TA_CENTER)
_bucket_label = ParagraphStyle("BucketLabel", parent=styles["Normal"], fontSize=10,
                                fontName="Helvetica-Bold", alignment=TA_CENTER)


def _fetch_map_image(lat: float, lon: float) -> Image | None:
    try:
        import httpx
        url = STATIC_MAP_URL.format(lat=lat, lon=lon)
        r = httpx.get(url, timeout=8, follow_redirects=True)
        if r.status_code == 200:
            buf = io.BytesIO(r.content)
            return Image(buf, width=4.8 * inch, height=2.4 * inch)
    except Exception:
        pass
    return None


def _criterion_row(c: dict) -> list:
    score = c.get("raw_score")
    bar_pct = int((score or 0) * 10)
    score_str = f"{score:.1f}/10" if score is not None else "—"
    status = c.get("status", "ok")
    status_color = {
        "ok": _SAGE, "flagged": _GOLD, "ineligible": _RUST, "data_unavailable": _TEXT_DIM
    }.get(status, _TEXT_DIM)
    return [
        Paragraph(c.get("name", c.get("key", "")), _body),
        Paragraph(score_str, ParagraphStyle("Score", parent=_body, textColor=status_color,
                                             fontName="Helvetica-Bold", alignment=TA_RIGHT)),
        Paragraph(f"{c.get('weight', 0) * 100:.0f}%", _dim),
        Paragraph(c.get("finding", "")[:200], _finding),
    ]


def generate_pdf(
    report: dict[str, Any],
    jurisdiction: dict[str, Any] | None = None,
    precedents: list[dict[str, Any]] | None = None,
    consultant_name: str | None = None,
) -> bytes:
    """Return PDF bytes for a SuitabilityReport dict.

    Args:
        report: SuitabilityReport.model_dump(mode='json')
        jurisdiction: Row from town_jurisdiction_risk (optional)
        precedents: List of precedent dicts for this town (optional)
        consultant_name: Consultant firm name for footer branding
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    story = []
    total_score = report.get("total_score") or 0
    bucket = report.get("bucket") or "CONSTRAINED"
    bucket_color = BUCKET_COLORS.get(bucket, _RUST)
    address = report.get("address") or report.get("parcel_id") or "Unknown Address"
    town = (report.get("resolution") or {}).get("resolved_town") or ""
    project_type = report.get("project_type") or "generic"
    computed_at = report.get("computed_at") or datetime.now(timezone.utc).isoformat()

    # ── PAGE 1: Cover ──────────────────────────────────────────────────────
    story.append(Paragraph("CIVO", ParagraphStyle("Brand", parent=_h1, fontSize=11,
                                                   textColor=_TEXT_DIM, spaceAfter=2)))
    story.append(Paragraph("Site Suitability Report", _h1))
    story.append(HRFlowable(width="100%", thickness=1, color=_BORDER, spaceAfter=12))

    story.append(Paragraph(address, ParagraphStyle("Addr", parent=_h1, fontSize=16,
                                                    textColor=colors.HexColor("#2C2825"))))
    if town:
        story.append(Paragraph(f"{town}, MA", _dim))
    story.append(Spacer(1, 0.2 * inch))

    # Score badge
    score_color = BUCKET_COLORS.get(bucket, _RUST)
    story.append(Paragraph(str(int(round(total_score))),
                            ParagraphStyle("ScoreBig", parent=_score_large, textColor=score_color)))
    bucket_display = "Conditional" if bucket == "CONDITIONALLY SUITABLE" else bucket.title()
    story.append(Paragraph(bucket_display.upper(),
                            ParagraphStyle("BucketBig", parent=_bucket_label, textColor=score_color,
                                           spaceAfter=12)))

    # Meta row
    meta_data = [
        ["Project type", project_type.replace("_", " ").title()],
        ["Config", report.get("config_version") or "—"],
        ["Computed", computed_at[:10]],
    ]
    if report.get("ineligible_flags"):
        meta_data.append(["Ineligible flags", ", ".join(report["ineligible_flags"])])

    meta_table = Table(meta_data, colWidths=[1.4 * inch, 4 * inch])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (0, -1), _TEXT_DIM),
        ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#2C2825")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.2 * inch))

    # Map
    lat = lon = None
    for c in report.get("criteria") or []:
        if c.get("key") == "grid_alignment":
            break
    res = report.get("resolution") or {}
    # Try to get lat/lon from parcel_id hint or skip map
    map_img = None
    story.append(Spacer(1, 0.1 * inch))
    if map_img:
        story.append(map_img)

    if consultant_name:
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph(f"Prepared by {consultant_name}", _dim))

    story.append(PageBreak())

    # ── PAGE 2: Criterion Breakdown ────────────────────────────────────────
    story.append(Paragraph("Criterion Breakdown", _h2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER, spaceAfter=8))

    criteria = report.get("criteria") or []
    if criteria:
        header = [
            Paragraph("Criterion", _label),
            Paragraph("Score", _label),
            Paragraph("Wt", _label),
            Paragraph("Finding", _label),
        ]
        rows = [header] + [_criterion_row(c) for c in criteria]
        col_widths = [1.6 * inch, 0.6 * inch, 0.4 * inch, 4.2 * inch]
        t = Table(rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _BG_LIGHT),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, _BORDER),
            ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#EDE9E3")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No criterion data available.", _dim))

    story.append(PageBreak())

    # ── PAGE 3: Constraints + Jurisdiction ────────────────────────────────
    story.append(Paragraph("Constraints & Jurisdiction", _h2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER, spaceAfter=8))

    # Ineligibility / constraint flags from report
    flags = report.get("ineligible_flags") or []
    if flags:
        story.append(Paragraph("Ineligibility Flags (225 CMR 29.06)", _label))
        for f in flags:
            story.append(Paragraph(f"• {f}", _body))
        story.append(Spacer(1, 0.1 * inch))

    # Jurisdiction risk
    if jurisdiction:
        story.append(Paragraph("Jurisdiction Risk", _label))
        jdata = [
            ["DOER adoption status", jurisdiction.get("doer_status") or "unknown"],
            ["Moratorium active", "YES — parcels in this town are suppressed in discovery" if jurisdiction.get("moratorium_active") else "No"],
            ["ConCom approval rate", f"{jurisdiction['concom_approval_rate']:.0%}" if jurisdiction.get("concom_approval_rate") is not None else "No data"],
            ["Median permit timeline", f"{jurisdiction['median_permit_days']} days" if jurisdiction.get("median_permit_days") else "No data"],
            ["Discovery risk multiplier", f"{jurisdiction.get('risk_multiplier', 1.0):.2f}"],
        ]
        jt = Table(jdata, colWidths=[2.0 * inch, 4.8 * inch])
        jt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (0, -1), _TEXT_DIM),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#EDE9E3")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(jt)

    story.append(PageBreak())

    # ── PAGE 4: Precedents + Next Steps ───────────────────────────────────
    story.append(Paragraph("Precedents & Next Steps", _h2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER, spaceAfter=8))

    precs = (precedents or [])[:5]
    if precs:
        story.append(Paragraph(f"Recent {town or 'town'} decisions (up to 5)", _label))
        for p in precs:
            decision = p.get("decision") or "unknown"
            dec_color = _SAGE if decision == "approved" else (_RUST if decision == "denied" else _TEXT_DIM)
            story.append(Paragraph(
                f"<b>{p.get('project_address') or p.get('docket') or '—'}</b> "
                f"— <font color='#{dec_color.hexval()[2:]}' size=8>{decision.upper()}</font> "
                f"({p.get('decision_date') or p.get('filing_date') or 'date unknown'})",
                _body,
            ))
            if p.get("conditions"):
                conds = p["conditions"][:3]
                story.append(Paragraph("Conditions: " + "; ".join(conds), _finding))
            story.append(Spacer(1, 0.06 * inch))
    else:
        story.append(Paragraph(f"No precedent decisions on record for {town or 'this town'}.", _dim))

    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Recommended Next Steps", _label))
    steps = [
        "Confirm parcel ownership and site control availability.",
        "File for pre-application meeting with Conservation Commission and Planning Board.",
        "Verify DOER model bylaw alignment and §3 exemption eligibility.",
        "Commission wetlands delineation if parcel borders MassDEP buffer zone.",
        "Request Eversource/National Grid hosting capacity confirmation for the nearest circuit.",
    ]
    for i, s in enumerate(steps, 1):
        story.append(Paragraph(f"{i}. {s}", _body))

    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
    story.append(Spacer(1, 0.05 * inch))
    footer_text = (
        f"Generated by Civo · {computed_at[:10]} · "
        f"Scored against {report.get('config_version') or 'ma-eea-2026-v1'} "
        f"(225 CMR 29.00). Not legal advice."
    )
    story.append(Paragraph(footer_text, _dim))

    doc.build(story)
    return buf.getvalue()
