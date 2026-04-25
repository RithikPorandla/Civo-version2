"""PDF report generation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_session
from app.services.pdf_report import generate_pdf

router = APIRouter(tags=["pdf"])


@router.get("/score/{report_id}/pdf")
def download_report_pdf(
    report_id: int,
    consultant: str = Query(default="", description="Consultant firm name for footer"),
    session: Session = Depends(get_session),
) -> Response:
    """Download a consultant-ready PDF for a scored parcel report."""
    row = session.execute(
        text("SELECT report, parcel_loc_id FROM score_history WHERE id = :id"),
        {"id": report_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    report_dict = dict(row["report"])

    # Fetch jurisdiction risk for the town
    town_name = report_dict.get("resolution", {}).get("resolved_town") or ""
    project_type = report_dict.get("project_type") or "bess_standalone"
    jurisdiction = None
    if town_name:
        jrow = session.execute(
            text("""
                SELECT risk_multiplier, moratorium_active, doer_status,
                       concom_approval_rate, median_permit_days
                FROM town_jurisdiction_risk
                WHERE town_name = :town AND project_type = :pt
                LIMIT 1
            """),
            {"town": town_name, "pt": project_type},
        ).mappings().first()
        if jrow:
            jurisdiction = dict(jrow)

    # Fetch recent precedents for the town
    precedents = []
    if town_name:
        prows = session.execute(
            text("""
                SELECT p.project_address, p.docket, p.decision, p.decision_date,
                       p.filing_date, p.conditions
                FROM precedents p
                JOIN municipalities m ON m.town_id = p.town_id
                WHERE m.town_name = :town
                ORDER BY COALESCE(p.decision_date, p.filing_date) DESC NULLS LAST
                LIMIT 5
            """),
            {"town": town_name},
        ).mappings().all()
        precedents = [dict(r) for r in prows]

    try:
        pdf_bytes = generate_pdf(
            report=report_dict,
            jurisdiction=jurisdiction,
            precedents=precedents,
            consultant_name=consultant or None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}") from exc

    filename = f"civo-report-{report_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
