"""Tiered rent estimation service: LLM → HUD FMR → RentCast."""

import asyncio
import hashlib
import json
import logging
from decimal import Decimal

from src.config import settings
from src.data.geocode import geocode_address
from src.data.hud import HUDClient
from src.data.rent_cache import RentCache
from src.data.rentcast import RentCastClient
from src.models.rent_estimate import HUDFairMarketRent, RentEstimate, TierResult

logger = logging.getLogger(__name__)

# Median sqft by bedroom count (national approximations for SFR)
MEDIAN_SQFT_BY_BEDS = {0: 500, 1: 750, 2: 1000, 3: 1400, 4: 1800, 5: 2200}

# Tier weights for confidence blending
TIER_WEIGHTS = {"llm": 0.3, "hud": 0.3, "rentcast": 0.4}

# Cost estimates per API call
TIER_COSTS = {"llm": 0.001, "hud": 0.0, "rentcast": 0.01}

# Cache TTLs in days
CACHE_TTL = {"llm": 7, "hud": 180, "rentcast": 30}


def _cache_key(address: str, beds: int, baths: float, sqft: int, tier: str) -> str:
    raw = f"{address.lower().strip()}|{beds}|{baths}|{sqft}|{tier}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _confidence_label(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


class RentEstimator:
    def __init__(self, db_path: str = "data/rent_cache.db"):
        self.cache = RentCache(db_path)
        self.hud_client = HUDClient()
        self.rentcast_client = RentCastClient()

    async def estimate_rent(
        self,
        address: str,
        beds: int,
        baths: float,
        sqft: int,
        property_type: str = "SFR",
        tier: str = "auto",
        serious: bool = False,
    ) -> RentEstimate:
        """Estimate rent using the specified tier strategy.

        Args:
            address: Full street address.
            beds: Number of bedrooms.
            baths: Number of bathrooms.
            sqft: Square footage.
            property_type: Property type (SFR, condo, etc.).
            tier: "auto", "llm", "hud", or "rentcast".
            serious: If True in auto mode, also runs Tier 3 (RentCast).
        """
        if tier == "auto":
            return await self._estimate_auto(address, beds, baths, sqft, property_type, serious)

        # Single-tier mode
        dispatch = {
            "llm": self._estimate_llm,
            "hud": self._estimate_hud,
            "rentcast": self._estimate_rentcast,
        }
        fn = dispatch.get(tier)
        if fn is None:
            raise ValueError(f"Unknown tier: {tier}")

        # Check cache
        key = _cache_key(address, beds, baths, sqft, tier)
        cached = self.cache.get_cached(key, tier)
        if cached:
            self.cache.log_usage(tier, address, 0.0, cache_hit=True)
            return RentEstimate(**cached)

        result = await fn(address, beds, baths, sqft, property_type)
        estimate = self._build_single_tier_estimate(address, result)

        self.cache.set_cached(key, tier, address, estimate.model_dump(), CACHE_TTL.get(tier, 7))
        self.cache.log_usage(tier, address, TIER_COSTS.get(tier, 0), cache_hit=False)
        return estimate

    async def _estimate_auto(
        self,
        address: str,
        beds: int,
        baths: float,
        sqft: int,
        property_type: str,
        serious: bool,
    ) -> RentEstimate:
        # Check for a cached auto result first
        key = _cache_key(address, beds, baths, sqft, "auto")
        cached = self.cache.get_cached(key, "auto")
        if cached:
            self.cache.log_usage("auto", address, 0.0, cache_hit=True)
            return RentEstimate(**cached)

        # Run Tier 1 + Tier 2 in parallel
        llm_task = self._estimate_llm(address, beds, baths, sqft, property_type)
        hud_task = self._estimate_hud(address, beds, baths, sqft, property_type)
        llm_result, hud_result = await asyncio.gather(llm_task, hud_task, return_exceptions=True)

        # Normalize exceptions to None TierResults
        if isinstance(llm_result, Exception):
            logger.warning("LLM tier failed: %s", llm_result)
            llm_result = TierResult(tier="llm", estimate=None, confidence="low", reasoning=f"Error: {llm_result}")
        if isinstance(hud_result, Exception):
            logger.warning("HUD tier failed: %s", hud_result)
            hud_result = TierResult(tier="hud", estimate=None, confidence="low", reasoning=f"Error: {hud_result}")

        tier_results = [llm_result, hud_result]
        needs_review = False

        # Compare T1 and T2 — flag if >20% apart
        if llm_result.estimate and hud_result.estimate:
            avg = (llm_result.estimate + hud_result.estimate) / 2
            diff_pct = abs(llm_result.estimate - hud_result.estimate) / avg if avg > 0 else 0
            if diff_pct > 0.20:
                needs_review = True

        # Optionally escalate to Tier 3
        rentcast_result = None
        if serious:
            try:
                rentcast_result = await self._estimate_rentcast(address, beds, baths, sqft, property_type)
                tier_results.append(rentcast_result)
            except Exception as e:
                logger.warning("RentCast tier failed: %s", e)
                tier_results.append(
                    TierResult(tier="rentcast", estimate=None, confidence="low", reasoning=f"Error: {e}")
                )

        estimate = self._blend_results(address, tier_results, needs_review)

        self.cache.set_cached(key, "auto", address, estimate.model_dump(), ttl_days=7)
        # Log usage for each tier that actually ran
        for tr in tier_results:
            if tr.estimate is not None:
                self.cache.log_usage(tr.tier, address, TIER_COSTS.get(tr.tier, 0), cache_hit=False)

        return estimate

    # ── Tier 1: LLM ──────────────────────────────────────────────

    async def _estimate_llm(
        self,
        address: str,
        beds: int,
        baths: float,
        sqft: int,
        property_type: str,
    ) -> TierResult:
        api_key = settings.anthropic_api_key
        if not api_key:
            return TierResult(tier="llm", estimate=None, confidence="low", reasoning="Anthropic API key not configured")

        try:
            import anthropic
        except ImportError:
            return TierResult(tier="llm", estimate=None, confidence="low", reasoning="anthropic package not installed")

        prompt = (
            f"Estimate the monthly rent for this property. Return ONLY valid JSON, no other text.\n\n"
            f"Address: {address}\n"
            f"Type: {property_type}\n"
            f"Bedrooms: {beds}\n"
            f"Bathrooms: {baths}\n"
            f"Square feet: {sqft}\n\n"
            f"Return JSON: {{\"rent_low\": <int>, \"rent_mid\": <int>, \"rent_high\": <int>, \"reasoning\": <str>}}"
        )

        try:
            client = anthropic.AsyncAnthropic(api_key=api_key)
            message = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text.strip()

            # Extract JSON from response (handle markdown code blocks)
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)
            rent_low = float(data["rent_low"])
            rent_mid = float(data["rent_mid"])
            rent_high = float(data["rent_high"])
            reasoning = data.get("reasoning", "")

            # Derive confidence from range width
            spread = (rent_high - rent_low) / rent_mid if rent_mid > 0 else 1.0
            if spread < 0.15:
                confidence = "high"
            elif spread < 0.30:
                confidence = "medium"
            else:
                confidence = "low"

            return TierResult(
                tier="llm",
                estimate=rent_mid,
                confidence=confidence,
                reasoning=reasoning,
            )
        except Exception as e:
            logger.warning("LLM rent estimation failed: %s", e)
            return TierResult(tier="llm", estimate=None, confidence="low", reasoning=f"Error: {e}")

    # ── Tier 2: HUD FMR ──────────────────────────────────────────

    async def _estimate_hud(
        self,
        address: str,
        beds: int,
        baths: float,
        sqft: int,
        property_type: str,
    ) -> TierResult:
        try:
            geo = await geocode_address(address)
        except Exception as e:
            return TierResult(tier="hud", estimate=None, confidence="low", reasoning=f"Geocoding failed: {e}")

        if not geo.state_fips or not geo.county_fips:
            return TierResult(tier="hud", estimate=None, confidence="low", reasoning="Missing FIPS codes")

        entity_id = f"{geo.state_fips}{geo.county_fips}99999"

        # Check HUD-specific cache
        cached_fmr = self.cache.get_hud_cached(entity_id)
        if cached_fmr:
            fmr = HUDFairMarketRent(**cached_fmr)
        else:
            fmr = await self.hud_client.get_fmr(geo.state_fips, geo.county_fips)
            if fmr is None:
                return TierResult(tier="hud", estimate=None, confidence="low", reasoning="HUD FMR data unavailable")
            self.cache.set_hud_cached(entity_id, fmr.model_dump())

        base_fmr = fmr.fmr_for_beds(beds)
        if base_fmr <= 0:
            return TierResult(tier="hud", estimate=None, confidence="low", reasoning="FMR is zero or negative")

        # Adjust by sqft relative to median
        median_sqft = MEDIAN_SQFT_BY_BEDS.get(min(beds, 5), 1400)
        sqft_ratio = sqft / median_sqft
        # Bound the adjustment to ±40%
        sqft_ratio = max(0.6, min(1.4, sqft_ratio))
        adjusted = round(base_fmr * sqft_ratio, 2)

        return TierResult(
            tier="hud",
            estimate=adjusted,
            confidence="medium",
            reasoning=f"FMR ${base_fmr:.0f} for {beds}br in {fmr.area_name}, adjusted by sqft ratio {sqft_ratio:.2f}",
        )

    # ── Tier 3: RentCast ──────────────────────────────────────────

    async def _estimate_rentcast(
        self,
        address: str,
        beds: int,
        baths: float,
        sqft: int,
        property_type: str,
    ) -> TierResult:
        # Rate limit check
        calls_this_month = self.cache.get_rentcast_calls_this_month()
        if calls_this_month >= settings.rentcast_monthly_limit:
            return TierResult(
                tier="rentcast",
                estimate=None,
                confidence="low",
                reasoning=f"Monthly RentCast limit reached ({calls_this_month}/{settings.rentcast_monthly_limit})",
            )

        try:
            geo = await geocode_address(address)
        except Exception as e:
            return TierResult(tier="rentcast", estimate=None, confidence="low", reasoning=f"Geocoding failed: {e}")

        rent = await self.rentcast_client.get_rent_estimate(geo)
        if rent is None:
            return TierResult(tier="rentcast", estimate=None, confidence="low", reasoning="RentCast returned no data")

        return TierResult(
            tier="rentcast",
            estimate=float(rent),
            confidence="high",
            reasoning="RentCast AVM rent estimate",
        )

    # ── Blending / result construction ────────────────────────────

    def _build_single_tier_estimate(self, address: str, result: TierResult) -> RentEstimate:
        est = result.estimate or 0.0
        conf_map = {"high": 0.8, "medium": 0.6, "low": 0.3}
        score = conf_map.get(result.confidence, 0.3)
        margin = est * (1 - score) * 0.3
        return RentEstimate(
            address=address,
            estimated_rent=est,
            confidence=result.confidence,
            confidence_score=score,
            needs_review=result.estimate is None,
            tier_results=[result],
            recommended_range=(round(est - margin, 2), round(est + margin, 2)),
        )

    def _blend_results(
        self, address: str, tier_results: list[TierResult], needs_review: bool
    ) -> RentEstimate:
        conf_map = {"high": 0.85, "medium": 0.6, "low": 0.3}

        # Collect valid estimates with their weights
        weighted_estimates: list[tuple[float, float]] = []
        for tr in tier_results:
            if tr.estimate is not None:
                weight = TIER_WEIGHTS.get(tr.tier, 0.2)
                weighted_estimates.append((tr.estimate, weight))

        if not weighted_estimates:
            return RentEstimate(
                address=address,
                estimated_rent=0.0,
                confidence="low",
                confidence_score=0.0,
                needs_review=True,
                tier_results=tier_results,
                recommended_range=(0.0, 0.0),
            )

        # Weighted average
        total_weight = sum(w for _, w in weighted_estimates)
        blended = sum(est * w for est, w in weighted_estimates) / total_weight

        # Confidence score: average of tier confidence scores, weighted
        weighted_conf = 0.0
        for tr in tier_results:
            if tr.estimate is not None:
                w = TIER_WEIGHTS.get(tr.tier, 0.2)
                weighted_conf += conf_map.get(tr.confidence, 0.3) * w
        confidence_score = weighted_conf / total_weight

        # Agreement bonus: if tiers are close, boost confidence
        estimates = [est for est, _ in weighted_estimates]
        if len(estimates) >= 2:
            avg = sum(estimates) / len(estimates)
            max_diff = max(abs(e - avg) / avg for e in estimates) if avg > 0 else 1.0
            if max_diff < 0.10:
                confidence_score = min(1.0, confidence_score + 0.1)
            elif max_diff > 0.25:
                confidence_score = max(0.0, confidence_score - 0.1)

        confidence_score = round(min(1.0, max(0.0, confidence_score)), 3)

        # Range from min/max of tier estimates with a confidence-based margin
        low_est = min(estimates)
        high_est = max(estimates)
        margin = blended * (1 - confidence_score) * 0.15
        recommended_range = (round(low_est - margin, 2), round(high_est + margin, 2))

        return RentEstimate(
            address=address,
            estimated_rent=round(blended, 2),
            confidence=_confidence_label(confidence_score),
            confidence_score=confidence_score,
            needs_review=needs_review,
            tier_results=tier_results,
            recommended_range=recommended_range,
        )
