"""Data-driven maintenance cost estimator.

Factors: property age, condition grade, climate zone, renter density.
Returns maintenance as a percentage of gross rent.
"""

from decimal import Decimal

from src.data.climate import ClimateZone
from src.models.smart_assumptions import AssumptionDetail, AssumptionSource, Confidence


# Base maintenance % by property age
def _age_base_pct(year_built: int) -> tuple[Decimal, str]:
    """Older properties need more maintenance."""
    import datetime
    age = datetime.date.today().year - year_built if year_built else 30

    if age <= 5:
        return Decimal("0.03"), f"New build ({age}yr)"
    if age <= 15:
        return Decimal("0.04"), f"Modern ({age}yr)"
    if age <= 30:
        return Decimal("0.05"), f"Established ({age}yr)"
    if age <= 50:
        return Decimal("0.07"), f"Aging ({age}yr)"
    if age <= 75:
        return Decimal("0.08"), f"Vintage ({age}yr)"
    return Decimal("0.10"), f"Historic ({age}yr)"


# Condition grade multiplier (how well maintained currently)
CONDITION_MULTIPLIERS: dict[str, tuple[Decimal, str]] = {
    "turnkey": (Decimal("0.85"), "turnkey condition"),
    "light": (Decimal("0.95"), "light rehab done"),
    "medium": (Decimal("1.0"), "medium condition"),
    "heavy": (Decimal("1.10"), "heavy wear"),
    "full_gut": (Decimal("1.20"), "gut rehab done — new systems"),
}

# Climate zone multiplier — extreme weather increases maintenance
CLIMATE_MULTIPLIERS: dict[ClimateZone, tuple[Decimal, str]] = {
    ClimateZone.HOT_HUMID: (Decimal("1.15"), "hot/humid climate (mold, HVAC wear)"),
    ClimateZone.HOT_DRY: (Decimal("1.05"), "hot/dry climate"),
    ClimateZone.MIXED_HUMID: (Decimal("1.0"), "mixed/humid climate"),
    ClimateZone.MIXED_DRY: (Decimal("0.95"), "mixed/dry climate"),
    ClimateZone.COLD: (Decimal("1.10"), "cold climate (freeze/thaw, heating)"),
    ClimateZone.VERY_COLD: (Decimal("1.15"), "very cold climate (freeze/thaw, snow load)"),
    ClimateZone.MARINE: (Decimal("1.0"), "marine climate"),
}


def estimate_maintenance_pct(
    year_built: int,
    condition_grade: str = "turnkey",
    climate_zone: ClimateZone = ClimateZone.MIXED_HUMID,
    renter_pct: Decimal | None = None,
) -> tuple[Decimal, AssumptionDetail]:
    """Estimate maintenance as % of gross rent.

    Returns (maintenance_pct, AssumptionDetail with breakdown).
    """
    base_pct, age_desc = _age_base_pct(year_built)
    components = [f"Age base: {float(base_pct)*100:.0f}% ({age_desc})"]

    # Condition
    cond_key = condition_grade.lower()
    cond_mult, cond_desc = CONDITION_MULTIPLIERS.get(
        cond_key, (Decimal("1.0"), "unknown condition")
    )
    components.append(f"Condition: {float(cond_mult):.2f}x ({cond_desc})")

    # Climate
    clim_mult, clim_desc = CLIMATE_MULTIPLIERS.get(
        climate_zone, (Decimal("1.0"), "unknown climate")
    )
    components.append(f"Climate: {float(clim_mult):.2f}x ({clim_desc})")

    # Renter density — high renter areas = more wear
    renter_mult = Decimal("1.0")
    renter_desc = "normal"
    if renter_pct is not None:
        if renter_pct > Decimal("0.70"):
            renter_mult = Decimal("1.10")
            renter_desc = f"high renter density ({float(renter_pct)*100:.0f}%)"
        elif renter_pct > Decimal("0.50"):
            renter_mult = Decimal("1.05")
            renter_desc = f"moderate renter density ({float(renter_pct)*100:.0f}%)"
    components.append(f"Renter wear: {float(renter_mult):.2f}x ({renter_desc})")

    result = base_pct * cond_mult * clim_mult * renter_mult
    result = result.quantize(Decimal("0.01"))

    # Clamp to reasonable range
    result = max(Decimal("0.03"), min(Decimal("0.15"), result))

    has_data = renter_pct is not None
    confidence = Confidence.MEDIUM if has_data else Confidence.LOW

    detail = AssumptionDetail(
        field_name="maintenance_pct",
        value=result,
        source=AssumptionSource.ESTIMATED,
        confidence=confidence,
        justification=f"Maintenance: {float(result)*100:.1f}% of gross rent. {'; '.join(components)}",
        data_points={
            "year_built": year_built,
            "condition_grade": condition_grade,
            "climate_zone": climate_zone.value,
            "renter_pct": float(renter_pct) if renter_pct else None,
        },
    )

    return result, detail
