"""SQLAlchemy ORM models for PostgreSQL persistence."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PropertyRecord(Base):
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Address
    street: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    zip_code: Mapped[str] = mapped_column(String(10))
    county: Mapped[str] = mapped_column(String(100), default="")
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=True)

    # Property details
    bedrooms: Mapped[int] = mapped_column(Integer, default=0)
    bathrooms: Mapped[Decimal] = mapped_column(Numeric(3, 1), default=0)
    sqft: Mapped[int] = mapped_column(Integer, default=0)
    year_built: Mapped[int] = mapped_column(Integer, default=0)
    lot_sqft: Mapped[int] = mapped_column(Integer, default=0)
    property_type: Mapped[str] = mapped_column(String(50), default="SFR")

    # Valuation
    estimated_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    estimated_rent: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    annual_tax: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)

    # Raw API response data for debugging
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    analyses: Mapped[list["AnalysisRecord"]] = relationship(back_populates="property")


class InvestorProfileRecord(Base):
    __tablename__ = "investor_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    name: Mapped[str] = mapped_column(String(100))
    filing_status: Mapped[str] = mapped_column(String(50))
    agi: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    marginal_federal_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    marginal_state_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    state: Mapped[str] = mapped_column(String(2))
    other_passive_income: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_re_professional: Mapped[bool] = mapped_column(Boolean, default=False)

    analyses: Mapped[list["AnalysisRecord"]] = relationship(back_populates="investor_profile")


class AnalysisRecord(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    investor_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investor_profiles.id"))

    # Assumptions snapshot (JSON for flexibility)
    assumptions: Mapped[dict] = mapped_column(JSON)

    # Summary results
    before_tax_irr: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=True)
    after_tax_irr: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=True)
    equity_multiple: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=True)
    total_profit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=True)

    # Full results (JSON)
    yearly_projections: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    disposition_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    property: Mapped["PropertyRecord"] = relationship(back_populates="analyses")
    investor_profile: Mapped["InvestorProfileRecord"] = relationship(back_populates="analyses")


class MacroDataPoint(Base):
    __tablename__ = "macro_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[str] = mapped_column(String(50), index=True)
    date: Mapped[datetime] = mapped_column(DateTime, index=True)
    value: Mapped[Decimal] = mapped_column(Numeric(15, 6))
    source: Mapped[str] = mapped_column(String(20))  # "fred", "census", etc.
