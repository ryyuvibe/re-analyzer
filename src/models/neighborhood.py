"""Neighborhood intelligence data types."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


@dataclass(frozen=True)
class NeighborhoodDemographics:
    median_household_income: int | None = None
    median_home_value: int | None = None
    poverty_rate: Decimal | None = None
    population: int | None = None
    renter_pct: Decimal | None = None


@dataclass(frozen=True)
class WalkScoreResult:
    walk_score: int | None = None
    transit_score: int | None = None
    bike_score: int | None = None


@dataclass(frozen=True)
class SchoolInfo:
    name: str
    rating: int  # 1-10
    level: str  # elementary / middle / high
    distance_miles: Decimal


class NeighborhoodGrade(Enum):
    A = "A"  # Premium
    B = "B"  # Good
    C = "C"  # Average / working class
    D = "D"  # Below average
    F = "F"  # Distressed


@dataclass(frozen=True)
class NeighborhoodReport:
    grade: NeighborhoodGrade
    grade_score: Decimal  # 0-100 composite
    demographics: NeighborhoodDemographics | None = None
    walk_score: WalkScoreResult | None = None
    schools: list[SchoolInfo] = field(default_factory=list)
    avg_school_rating: Decimal | None = None
    ai_narrative: str | None = None

    # Hazard data (populated by extended resolver)
    flood_zone: str | None = None
    seismic_pga: Decimal | None = None
    wildfire_risk: int | None = None
    hurricane_zone: int | None = None
    hail_frequency: str | None = None
    crime_rate: Decimal | None = None
    climate_zone: str | None = None
    traffic_noise_score: int | None = None
