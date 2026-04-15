"""SQLAlchemy ORM models for Civo's MA-specific permitting database.

All geometry columns are stored in EPSG:26986 (MA State Plane, meters) per
CLAUDE.md. GiST indexes are declared inline so Alembic autogenerate picks them
up. JSONB is used for any Claude-populated structured blobs that evolve faster
than the schema.
"""

from __future__ import annotations

from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.types import Vector

SRID = 26986


# ---------------------------------------------------------------------------
# Parcels (MassGIS L3 Property Tax Parcels)
# ---------------------------------------------------------------------------
class Parcel(Base):
    __tablename__ = "parcels"

    loc_id: Mapped[str] = mapped_column(String, primary_key=True)
    map_par_id: Mapped[str | None] = mapped_column(String)
    prop_id: Mapped[str | None] = mapped_column(String)
    town_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    town_name: Mapped[str] = mapped_column(String, nullable=False)
    poly_type: Mapped[str | None] = mapped_column(String)
    site_addr: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    zip: Mapped[str | None] = mapped_column(String)
    owner1: Mapped[str | None] = mapped_column(String)
    use_code: Mapped[str | None] = mapped_column(String)
    lot_size: Mapped[float | None] = mapped_column(Float)
    total_val: Mapped[int | None] = mapped_column(BigInteger)
    fy: Mapped[int | None] = mapped_column(Integer)
    shape_area: Mapped[float | None] = mapped_column(Float)
    raw: Mapped[dict | None] = mapped_column(JSONB)
    geom = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=SRID, spatial_index=True),
        nullable=False,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Habitat and ecological constraint layers (MassGIS)
# ---------------------------------------------------------------------------
def _polygon_column() -> "Mapped":
    return mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=SRID, spatial_index=True),
        nullable=False,
    )


class HabitatBiomapCore(Base):
    """BioMap Core Habitat — ineligible for generation/storage per 225 CMR 29.00."""

    __tablename__ = "habitat_biomap_core"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    core_id: Mapped[str | None] = mapped_column(String, index=True)
    core_name: Mapped[str | None] = mapped_column(String)
    core_type: Mapped[str | None] = mapped_column(String)
    source_version: Mapped[str | None] = mapped_column(String)
    attrs: Mapped[dict | None] = mapped_column(JSONB)
    geom = _polygon_column()


class HabitatBiomapCNL(Base):
    """BioMap Critical Natural Landscape."""

    __tablename__ = "habitat_biomap_cnl"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cnl_id: Mapped[str | None] = mapped_column(String, index=True)
    cnl_name: Mapped[str | None] = mapped_column(String)
    cnl_type: Mapped[str | None] = mapped_column(String)
    source_version: Mapped[str | None] = mapped_column(String)
    attrs: Mapped[dict | None] = mapped_column(JSONB)
    geom = _polygon_column()


class HabitatNHESPPriority(Base):
    """NHESP Priority Habitat of Rare Species — ineligible."""

    __tablename__ = "habitat_nhesp_priority"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    priority_id: Mapped[str | None] = mapped_column(String, index=True)
    source_version: Mapped[str | None] = mapped_column(String)
    attrs: Mapped[dict | None] = mapped_column(JSONB)
    geom = _polygon_column()


class HabitatNHESPEstimated(Base):
    """NHESP Estimated Habitat of Rare Wildlife (Wetlands Protection Act)."""

    __tablename__ = "habitat_nhesp_estimated"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    estimated_id: Mapped[str | None] = mapped_column(String, index=True)
    source_version: Mapped[str | None] = mapped_column(String)
    attrs: Mapped[dict | None] = mapped_column(JSONB)
    geom = _polygon_column()


# ---------------------------------------------------------------------------
# Flood, wetlands, farmland, open space
# ---------------------------------------------------------------------------
class FloodZone(Base):
    """FEMA NFHL flood hazard polygons."""

    __tablename__ = "flood_zones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fld_zone: Mapped[str | None] = mapped_column(String, index=True)
    zone_subty: Mapped[str | None] = mapped_column(String)
    sfha_tf: Mapped[str | None] = mapped_column(String)
    static_bfe: Mapped[float | None] = mapped_column(Float)
    dfirm_id: Mapped[str | None] = mapped_column(String)
    attrs: Mapped[dict | None] = mapped_column(JSONB)
    geom = _polygon_column()


class Wetland(Base):
    """MassDEP Wetlands (wetland resource areas — 310 CMR 10.04)."""

    __tablename__ = "wetlands"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iw_type: Mapped[str | None] = mapped_column(String, index=True)
    iw_class: Mapped[str | None] = mapped_column(String)
    source: Mapped[str | None] = mapped_column(String)
    attrs: Mapped[dict | None] = mapped_column(JSONB)
    geom = _polygon_column()


class PrimeFarmland(Base):
    """USDA NRCS Prime Farmland soils (also tracks farmland of statewide importance)."""

    __tablename__ = "prime_farmland"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    farmland_class: Mapped[str | None] = mapped_column(String, index=True)
    musym: Mapped[str | None] = mapped_column(String)
    muname: Mapped[str | None] = mapped_column(String)
    attrs: Mapped[dict | None] = mapped_column(JSONB)
    geom = _polygon_column()


class Article97(Base):
    """Article 97 protected open space — ineligible for generation/storage."""

    __tablename__ = "article97"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_name: Mapped[str | None] = mapped_column(String)
    owner_type: Mapped[str | None] = mapped_column(String, index=True)
    owner_name: Mapped[str | None] = mapped_column(String)
    attrs: Mapped[dict | None] = mapped_column(JSONB)
    geom = _polygon_column()


class LandUse(Base):
    """MassGIS 2016 Land Cover / Land Use polygons."""

    __tablename__ = "land_use"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    town_id: Mapped[int | None] = mapped_column(Integer, index=True)
    covercode: Mapped[int | None] = mapped_column(Integer, index=True)
    covername: Mapped[str | None] = mapped_column(String)
    usegencode: Mapped[int | None] = mapped_column(Integer, index=True)
    usegenname: Mapped[str | None] = mapped_column(String)
    use_code: Mapped[str | None] = mapped_column(String)
    poly_type: Mapped[str | None] = mapped_column(String)
    fy: Mapped[int | None] = mapped_column(Integer)
    shape_area: Mapped[float | None] = mapped_column(Float)
    attrs: Mapped[dict | None] = mapped_column(JSONB)
    geom = _polygon_column()


class MassEnviroScreen(Base):
    """MassEnviroScreen cumulative burden at block-group level."""

    __tablename__ = "massenviroscreen"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    geoid: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    ej_designation: Mapped[str | None] = mapped_column(String, index=True)
    cumulative_score: Mapped[float | None] = mapped_column(Float)
    pollution_score: Mapped[float | None] = mapped_column(Float)
    vulnerability_score: Mapped[float | None] = mapped_column(Float)
    attrs: Mapped[dict | None] = mapped_column(JSONB)
    geom = _polygon_column()


# ---------------------------------------------------------------------------
# Eversource ESMP projects (point geometry, 29 projects from DPU 24-10)
# ---------------------------------------------------------------------------
class ESMPProject(Base):
    __tablename__ = "esmp_projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_name: Mapped[str] = mapped_column(String, nullable=False)
    sub_region: Mapped[str | None] = mapped_column(String, index=True)
    isd: Mapped[str | None] = mapped_column(String)
    mw: Mapped[float | None] = mapped_column(Numeric(10, 2))
    project_type: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    siting_status: Mapped[str | None] = mapped_column(String, index=True)
    coordinate_confidence: Mapped[str | None] = mapped_column(String)
    in_service_date: Mapped[date | None] = mapped_column(Date)
    municipality: Mapped[str | None] = mapped_column(String, index=True)
    source_filing: Mapped[str] = mapped_column(String, nullable=False, default="DPU 24-10")
    attrs: Mapped[dict | None] = mapped_column(JSONB)
    geom = mapped_column(
        Geometry(geometry_type="POINT", srid=SRID, spatial_index=True), nullable=False
    )


# ---------------------------------------------------------------------------
# Municipalities + research-agent precedents
# ---------------------------------------------------------------------------
class Municipality(Base):
    __tablename__ = "municipalities"
    town_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    town_name: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    county: Mapped[str | None] = mapped_column(String)
    population: Mapped[int | None] = mapped_column(Integer)
    fips_code: Mapped[str | None] = mapped_column(String)
    town_url: Mapped[str | None] = mapped_column(String)
    planning_board: Mapped[dict | None] = mapped_column(JSONB)
    conservation_commission: Mapped[dict | None] = mapped_column(JSONB)
    zoning_board: Mapped[dict | None] = mapped_column(JSONB)
    building_department: Mapped[dict | None] = mapped_column(JSONB)
    bylaws: Mapped[dict | None] = mapped_column(JSONB)
    project_type_bylaws: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    moratoriums: Mapped[dict | None] = mapped_column(JSONB)
    political_signals: Mapped[dict | None] = mapped_column(JSONB)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    precedents: Mapped[list["Precedent"]] = relationship(back_populates="municipality")


class Precedent(Base):
    __tablename__ = "precedents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    town_id: Mapped[int | None] = mapped_column(ForeignKey("municipalities.town_id"), index=True)
    docket: Mapped[str | None] = mapped_column(String, index=True)
    project_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_address: Mapped[str | None] = mapped_column(String)
    parcel_loc_id: Mapped[str | None] = mapped_column(ForeignKey("parcels.loc_id"))
    applicant: Mapped[str | None] = mapped_column(String)
    decision: Mapped[str | None] = mapped_column(String, index=True)
    conditions: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    filing_date: Mapped[date | None] = mapped_column(Date)
    decision_date: Mapped[date | None] = mapped_column(Date)
    meeting_body: Mapped[str | None] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    full_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    embedding = mapped_column(Vector(1024))
    geom = mapped_column(
        Geometry(geometry_type="POINT", srid=SRID, spatial_index=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    municipality: Mapped["Municipality | None"] = relationship(back_populates="precedents")


# ---------------------------------------------------------------------------
# Score history (append-only audit of every /score call)
# ---------------------------------------------------------------------------
class Portfolio(Base):
    """A saved, shareable batch-scoring run.

    Items are denormalized — scores stay fixed until the user explicitly
    re-runs the portfolio, even if the underlying parcel is re-scored.
    ``config_version`` lets us reproduce the exact methodology used.
    """

    __tablename__ = "portfolios"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. 'port_abc123xyz'
    state: Mapped[str] = mapped_column(String, nullable=False, default="MA")
    name: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    items: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    project_type: Mapped[str | None] = mapped_column(String)
    config_version: Mapped[str] = mapped_column(String, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ScoreHistory(Base):
    __tablename__ = "score_history"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parcel_loc_id: Mapped[str | None] = mapped_column(ForeignKey("parcels.loc_id"), index=True)
    address: Mapped[str | None] = mapped_column(String)
    config_version: Mapped[str] = mapped_column(String, nullable=False, index=True)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    bucket: Mapped[str] = mapped_column(String, nullable=False)
    report: Mapped[dict] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
