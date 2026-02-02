"""Composite insurance risk model for rental properties.

6-layer hazard model: flood, earthquake, wildfire, hurricane/wind, hail, crime.
Plus property factors (age, type).

Each risk factor is a multiplier on the base rate, and contributes to the
AssumptionManifest tooltip explaining the estimate.
"""

from decimal import Decimal

from src.models.smart_assumptions import AssumptionDetail, AssumptionSource, Confidence

BASE_RATE = Decimal("0.0035")  # 0.35% of replacement cost
REPLACEMENT_COST_PCT = Decimal("0.80")  # Replacement cost ~ 80% of market value
MINIMUM_ANNUAL = Decimal("800")

# Legacy state multipliers — kept for backward-compatible simple estimator
_STATE_MULTIPLIERS: dict[str, Decimal] = {
    "FL": Decimal("1.40"), "LA": Decimal("1.40"), "TX": Decimal("1.40"),
    "MS": Decimal("1.30"), "SC": Decimal("1.25"), "NC": Decimal("1.20"),
    "AL": Decimal("1.25"), "CA": Decimal("1.30"), "CO": Decimal("1.15"),
    "OK": Decimal("1.25"), "KS": Decimal("1.20"),
}


# ------------------------------------------------------------------
# Backward-compatible simple estimator (used by existing tests/code)
# ------------------------------------------------------------------

def estimate_annual_insurance(
    property_value: Decimal,
    sqft: int,
    year_built: int,
    state: str = "OH",
    property_type: str = "SFR",
) -> Decimal:
    """Simple insurance estimate — base rate with state/age/type multipliers.

    This is the legacy interface kept for backward compatibility.
    For the full composite model, use estimate_insurance_composite().
    """
    premium = property_value * BASE_RATE

    state_mult = _STATE_MULTIPLIERS.get(state.upper(), Decimal("1.0"))
    premium *= state_mult

    if year_built and year_built < 1950:
        premium *= Decimal("1.20")
    elif year_built and year_built < 1970:
        premium *= Decimal("1.10")

    prop_upper = property_type.upper().replace("-", "").replace(" ", "")
    if prop_upper in ("MULTIFAMILY", "MULTI"):
        premium *= Decimal("1.15")
    elif prop_upper == "CONDO":
        premium *= Decimal("0.80")

    if premium < MINIMUM_ANNUAL:
        premium = MINIMUM_ANNUAL

    return premium.quantize(Decimal("1"))


# ------------------------------------------------------------------
# Composite 6-layer hazard model
# ------------------------------------------------------------------

# Flood multipliers by zone
FLOOD_MULTIPLIERS: dict[str, Decimal] = {
    "V": Decimal("2.0"), "VE": Decimal("2.0"),
    "A": Decimal("1.5"), "AE": Decimal("1.5"), "AH": Decimal("1.5"), "AO": Decimal("1.5"),
    "A99": Decimal("1.3"),
    "X500": Decimal("1.15"), "B": Decimal("1.15"),
    "X": Decimal("1.0"), "C": Decimal("1.0"), "D": Decimal("1.0"),
}

# Earthquake multipliers by PGA threshold
def _earthquake_multiplier(pga: Decimal | None) -> tuple[Decimal, str]:
    if pga is None:
        return Decimal("1.0"), "no data"
    if pga >= Decimal("0.4"):
        return Decimal("1.40"), f"high risk (PGA {pga}g)"
    if pga >= Decimal("0.2"):
        return Decimal("1.20"), f"moderate risk (PGA {pga}g)"
    return Decimal("1.0"), f"low risk (PGA {pga}g)"

# Wildfire multipliers by risk class (1-5)
WILDFIRE_MULTIPLIERS: dict[int, Decimal] = {
    5: Decimal("1.35"), 4: Decimal("1.20"), 3: Decimal("1.10"),
    2: Decimal("1.0"), 1: Decimal("1.0"),
}

# Hurricane/wind multipliers
def _hurricane_multiplier(zone: int) -> tuple[Decimal, str]:
    if zone >= 3:
        return Decimal("1.30"), f"Cat 3+ zone"
    if zone >= 1:
        return Decimal("1.15"), f"Cat 1-2 zone"
    return Decimal("1.0"), "inland"

# Hail multipliers
HAIL_MULTIPLIERS: dict[str, Decimal] = {
    "high": Decimal("1.15"),
    "moderate": Decimal("1.08"),
    "low": Decimal("1.0"),
}

# Crime/theft multiplier thresholds (property crime per 100K)
def _crime_multiplier(crime_rate: Decimal | None) -> tuple[Decimal, str]:
    if crime_rate is None:
        return Decimal("1.0"), "no data"
    rate = float(crime_rate)
    if rate > 3500:
        return Decimal("1.15"), f"high property crime ({rate:.0f}/100K)"
    if rate > 2000:
        return Decimal("1.05"), f"moderate property crime ({rate:.0f}/100K)"
    return Decimal("1.0"), f"low property crime ({rate:.0f}/100K)"


def estimate_insurance_composite(
    property_value: Decimal,
    year_built: int,
    property_type: str = "SFR",
    flood_zone: str | None = None,
    seismic_pga: Decimal | None = None,
    wildfire_risk: int | None = None,
    hurricane_zone: int = 0,
    hail_frequency: str = "low",
    crime_rate: Decimal | None = None,
) -> tuple[Decimal, AssumptionDetail]:
    """Composite insurance estimate using 6-layer hazard model.

    Returns (premium, AssumptionDetail with full breakdown).
    """
    # Base: 0.35% of replacement cost (80% of market value)
    replacement_cost = property_value * REPLACEMENT_COST_PCT
    premium = replacement_cost * BASE_RATE

    components = []
    total_multiplier = Decimal("1.0")

    # 1. Flood
    fz = (flood_zone or "X").upper()
    flood_mult = FLOOD_MULTIPLIERS.get(fz, Decimal("1.0"))
    total_multiplier *= flood_mult
    if flood_mult != Decimal("1.0"):
        pct = int((float(flood_mult) - 1) * 100)
        components.append(f"Flood zone {fz} (+{pct}%)")

    # 2. Earthquake
    eq_mult, eq_desc = _earthquake_multiplier(seismic_pga)
    total_multiplier *= eq_mult
    if eq_mult != Decimal("1.0"):
        pct = int((float(eq_mult) - 1) * 100)
        components.append(f"Seismic {eq_desc} (+{pct}%)")

    # 3. Wildfire
    wf_risk = wildfire_risk if wildfire_risk is not None else 1
    wf_mult = WILDFIRE_MULTIPLIERS.get(wf_risk, Decimal("1.0"))
    total_multiplier *= wf_mult
    if wf_mult != Decimal("1.0"):
        pct = int((float(wf_mult) - 1) * 100)
        components.append(f"Wildfire risk {wf_risk} (+{pct}%)")

    # 4. Hurricane/wind
    hurr_mult, hurr_desc = _hurricane_multiplier(hurricane_zone)
    total_multiplier *= hurr_mult
    if hurr_mult != Decimal("1.0"):
        pct = int((float(hurr_mult) - 1) * 100)
        components.append(f"Hurricane {hurr_desc} (+{pct}%)")

    # 5. Hail
    hail_mult = HAIL_MULTIPLIERS.get(hail_frequency, Decimal("1.0"))
    total_multiplier *= hail_mult
    if hail_mult != Decimal("1.0"):
        pct = int((float(hail_mult) - 1) * 100)
        components.append(f"Hail {hail_frequency} frequency (+{pct}%)")

    # 6. Crime/theft
    crime_mult, crime_desc = _crime_multiplier(crime_rate)
    total_multiplier *= crime_mult
    if crime_mult != Decimal("1.0"):
        pct = int((float(crime_mult) - 1) * 100)
        components.append(f"Crime {crime_desc} (+{pct}%)")

    # Property factors
    age_mult = Decimal("1.0")
    if year_built and year_built < 1950:
        age_mult = Decimal("1.20")
        components.append("Pre-1950 building (+20%)")
    elif year_built and year_built < 1970:
        age_mult = Decimal("1.10")
        components.append("Pre-1970 building (+10%)")
    total_multiplier *= age_mult

    prop_upper = property_type.upper().replace("-", "").replace(" ", "")
    type_mult = Decimal("1.0")
    if prop_upper in ("MULTIFAMILY", "MULTI"):
        type_mult = Decimal("1.15")
        components.append("Multi-family (+15%)")
    elif prop_upper == "CONDO":
        type_mult = Decimal("0.80")
        components.append("Condo (HOA covers structure, -20%)")
    total_multiplier *= type_mult

    premium *= total_multiplier
    premium = premium.quantize(Decimal("1"))

    # Determine confidence
    has_hazard_data = any([
        flood_zone is not None,
        seismic_pga is not None,
        wildfire_risk is not None,
    ])
    if has_hazard_data:
        confidence = Confidence.MEDIUM
        source = AssumptionSource.ESTIMATED
    else:
        confidence = Confidence.LOW
        source = AssumptionSource.DEFAULT

    # Flag very low estimates
    if premium < Decimal("400"):
        confidence = Confidence.LOW

    base_str = f"Base: {float(BASE_RATE)*100:.2f}% of replacement cost (${float(replacement_cost):,.0f})"
    if components:
        risk_str = "; ".join(components)
        justification = f"{base_str}. Risk factors: {risk_str}. Total: ${float(premium):,.0f}/yr"
    else:
        justification = f"{base_str}. No hazard surcharges. Total: ${float(premium):,.0f}/yr"

    detail = AssumptionDetail(
        field_name="insurance",
        value=premium,
        source=source,
        confidence=confidence,
        justification=justification,
        data_points={
            "flood_zone": fz,
            "seismic_pga": float(seismic_pga) if seismic_pga else None,
            "wildfire_risk": wf_risk,
            "hurricane_zone": hurricane_zone,
            "hail_frequency": hail_frequency,
            "crime_rate": float(crime_rate) if crime_rate else None,
            "total_multiplier": float(total_multiplier),
        },
    )

    return premium, detail
