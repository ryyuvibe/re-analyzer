"""Tests for the tiered rent estimation service."""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.data.rent_cache import RentCache
from src.data.rent_estimator import RentEstimator
from src.models.property import Address
from src.models.rent_estimate import HUDFairMarketRent, RentEstimate, TierResult


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test_cache.db")


@pytest.fixture
def estimator(tmp_db):
    return RentEstimator(db_path=tmp_db)


@pytest.fixture
def cache(tmp_db):
    return RentCache(tmp_db)


@pytest.fixture
def sample_address():
    return Address(
        street="123 Main St",
        city="Columbus",
        state="OH",
        zip_code="43215",
        county="Franklin",
        state_fips="39",
        county_fips="049",
        tract_fips="001100",
    )


@pytest.fixture
def sample_fmr():
    return HUDFairMarketRent(
        entity_id="3904999999",
        area_name="Franklin County, OH",
        year=2025,
        fmr_0br=800.0,
        fmr_1br=900.0,
        fmr_2br=1100.0,
        fmr_3br=1450.0,
        fmr_4br=1700.0,
    )


# ── Cache tests ──────────────────────────────────────────────────

class TestRentCache:
    def test_cache_miss(self, cache):
        assert cache.get_cached("nonexistent", "llm") is None

    def test_cache_set_and_get(self, cache):
        data = {"estimated_rent": 1500}
        cache.set_cached("key1", "llm", "123 Main St", data, ttl_days=7)
        result = cache.get_cached("key1", "llm")
        assert result == data

    def test_cache_different_tier(self, cache):
        cache.set_cached("key1", "llm", "123 Main St", {"rent": 1500}, ttl_days=7)
        assert cache.get_cached("key1", "hud") is None

    def test_hud_cache(self, cache):
        fmr_data = {"entity_id": "3904999999", "fmr_3br": 1450.0}
        cache.set_hud_cached("3904999999", fmr_data)
        result = cache.get_hud_cached("3904999999")
        assert result == fmr_data

    def test_usage_logging(self, cache):
        cache.log_usage("llm", "123 Main St", 0.001, cache_hit=False)
        cache.log_usage("llm", "456 Oak Ave", 0.001, cache_hit=False)
        cache.log_usage("llm", "123 Main St", 0.0, cache_hit=True)
        stats = cache.get_usage_stats()
        assert stats.total_calls == 3
        assert stats.cache_hits == 1
        assert stats.calls_by_tier["llm"] == 3

    def test_rentcast_monthly_count(self, cache):
        cache.log_usage("rentcast", "addr1", 0.01, cache_hit=False)
        cache.log_usage("rentcast", "addr2", 0.01, cache_hit=False)
        cache.log_usage("rentcast", "addr3", 0.0, cache_hit=True)  # cache hit shouldn't count
        assert cache.get_rentcast_calls_this_month() == 2


# ── Model tests ──────────────────────────────────────────────────

class TestModels:
    def test_fmr_for_beds(self, sample_fmr):
        assert sample_fmr.fmr_for_beds(0) == 800.0
        assert sample_fmr.fmr_for_beds(3) == 1450.0
        assert sample_fmr.fmr_for_beds(5) == 1700.0  # capped at 4

    def test_tier_result_serialization(self):
        tr = TierResult(tier="llm", estimate=1500.0, confidence="medium", reasoning="test")
        data = tr.model_dump()
        assert data["tier"] == "llm"
        assert data["estimate"] == 1500.0

    def test_rent_estimate_serialization(self):
        est = RentEstimate(
            address="123 Main St",
            estimated_rent=1500.0,
            confidence="medium",
            confidence_score=0.65,
            needs_review=False,
            tier_results=[],
            recommended_range=(1400.0, 1600.0),
        )
        data = est.model_dump()
        assert data["estimated_rent"] == 1500.0
        assert data["recommended_range"] == (1400.0, 1600.0)


# ── LLM tier tests ──────────────────────────────────────────────

class TestLLMTier:
    async def test_llm_no_api_key(self, estimator):
        with patch("src.data.rent_estimator.settings") as mock_settings:
            mock_settings.anthropic_api_key = ""
            result = await estimator._estimate_llm("123 Main St", 3, 1.5, 1200, "SFR")
            assert result.tier == "llm"
            assert result.estimate is None

    async def test_llm_success(self, estimator):
        llm_response = json.dumps({
            "rent_low": 1300,
            "rent_mid": 1500,
            "rent_high": 1700,
            "reasoning": "Based on Columbus OH market data",
        })

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=llm_response)]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        with (
            patch("src.data.rent_estimator.settings") as mock_settings,
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            mock_settings.anthropic_api_key = "test-key"
            result = await estimator._estimate_llm("123 Main St", 3, 1.5, 1200, "SFR")

        assert result.tier == "llm"
        assert result.estimate == 1500.0
        assert result.confidence in ("low", "medium", "high")


# ── HUD tier tests ───────────────────────────────────────────────

class TestHUDTier:
    async def test_hud_success(self, estimator, sample_address, sample_fmr):
        with (
            patch("src.data.rent_estimator.geocode_address", new_callable=AsyncMock, return_value=sample_address),
            patch.object(estimator.hud_client, "get_fmr", new_callable=AsyncMock, return_value=sample_fmr),
        ):
            result = await estimator._estimate_hud("123 Main St, Columbus, OH 43215", 3, 1.5, 1200, "SFR")

        assert result.tier == "hud"
        assert result.estimate is not None
        assert result.estimate > 0
        assert "FMR" in result.reasoning

    async def test_hud_geocode_failure(self, estimator):
        with patch(
            "src.data.rent_estimator.geocode_address",
            new_callable=AsyncMock,
            side_effect=ValueError("bad address"),
        ):
            result = await estimator._estimate_hud("bad address", 3, 1.5, 1200, "SFR")

        assert result.estimate is None
        assert "Geocoding failed" in result.reasoning

    async def test_hud_sqft_adjustment(self, estimator, sample_address, sample_fmr):
        """Larger sqft should produce a higher adjusted estimate."""
        with (
            patch("src.data.rent_estimator.geocode_address", new_callable=AsyncMock, return_value=sample_address),
            patch.object(estimator.hud_client, "get_fmr", new_callable=AsyncMock, return_value=sample_fmr),
        ):
            result_small = await estimator._estimate_hud("addr", 3, 1.5, 800, "SFR")
            result_large = await estimator._estimate_hud("addr", 3, 1.5, 1800, "SFR")

        assert result_large.estimate > result_small.estimate


# ── RentCast tier tests ──────────────────────────────────────────

class TestRentCastTier:
    async def test_rentcast_success(self, estimator, sample_address):
        with (
            patch("src.data.rent_estimator.geocode_address", new_callable=AsyncMock, return_value=sample_address),
            patch.object(
                estimator.rentcast_client,
                "get_rent_estimate",
                new_callable=AsyncMock,
                return_value=Decimal("1550"),
            ),
            patch("src.data.rent_estimator.settings") as mock_settings,
        ):
            mock_settings.rentcast_monthly_limit = 500
            result = await estimator._estimate_rentcast("123 Main St", 3, 1.5, 1200, "SFR")

        assert result.tier == "rentcast"
        assert result.estimate == 1550.0

    async def test_rentcast_rate_limited(self, estimator, tmp_db):
        cache = RentCache(tmp_db)
        # Log enough calls to hit the limit
        for i in range(500):
            cache.log_usage("rentcast", f"addr{i}", 0.01, cache_hit=False)

        with patch("src.data.rent_estimator.settings") as mock_settings:
            mock_settings.rentcast_monthly_limit = 500
            result = await estimator._estimate_rentcast("123 Main St", 3, 1.5, 1200, "SFR")

        assert result.estimate is None
        assert "limit reached" in result.reasoning


# ── Auto tier tests ──────────────────────────────────────────────

class TestAutoTier:
    async def test_auto_blends_results(self, estimator):
        llm_result = TierResult(tier="llm", estimate=1500.0, confidence="medium", reasoning="LLM estimate")
        hud_result = TierResult(tier="hud", estimate=1400.0, confidence="medium", reasoning="HUD estimate")

        with (
            patch.object(estimator, "_estimate_llm", new_callable=AsyncMock, return_value=llm_result),
            patch.object(estimator, "_estimate_hud", new_callable=AsyncMock, return_value=hud_result),
        ):
            result = await estimator._estimate_auto("123 Main St", 3, 1.5, 1200, "SFR", serious=False)

        assert result.estimated_rent > 0
        assert len(result.tier_results) == 2
        assert 1400 <= result.estimated_rent <= 1500

    async def test_auto_flags_disagreement(self, estimator):
        llm_result = TierResult(tier="llm", estimate=1500.0, confidence="medium", reasoning="LLM")
        hud_result = TierResult(tier="hud", estimate=2000.0, confidence="medium", reasoning="HUD")

        with (
            patch.object(estimator, "_estimate_llm", new_callable=AsyncMock, return_value=llm_result),
            patch.object(estimator, "_estimate_hud", new_callable=AsyncMock, return_value=hud_result),
        ):
            result = await estimator._estimate_auto("123 Main St", 3, 1.5, 1200, "SFR", serious=False)

        assert result.needs_review is True

    async def test_auto_with_serious(self, estimator):
        llm_result = TierResult(tier="llm", estimate=1500.0, confidence="medium", reasoning="LLM")
        hud_result = TierResult(tier="hud", estimate=1400.0, confidence="medium", reasoning="HUD")
        rc_result = TierResult(tier="rentcast", estimate=1550.0, confidence="high", reasoning="RentCast")

        with (
            patch.object(estimator, "_estimate_llm", new_callable=AsyncMock, return_value=llm_result),
            patch.object(estimator, "_estimate_hud", new_callable=AsyncMock, return_value=hud_result),
            patch.object(estimator, "_estimate_rentcast", new_callable=AsyncMock, return_value=rc_result),
        ):
            result = await estimator._estimate_auto("123 Main St", 3, 1.5, 1200, "SFR", serious=True)

        assert len(result.tier_results) == 3

    async def test_caching_works(self, estimator):
        llm_result = TierResult(tier="llm", estimate=1500.0, confidence="medium", reasoning="LLM")
        hud_result = TierResult(tier="hud", estimate=1400.0, confidence="medium", reasoning="HUD")

        with (
            patch.object(estimator, "_estimate_llm", new_callable=AsyncMock, return_value=llm_result) as mock_llm,
            patch.object(estimator, "_estimate_hud", new_callable=AsyncMock, return_value=hud_result) as mock_hud,
        ):
            result1 = await estimator.estimate_rent("123 Main St", 3, 1.5, 1200)
            result2 = await estimator.estimate_rent("123 Main St", 3, 1.5, 1200)

        # Second call should use cache — tier functions called only once
        assert mock_llm.call_count == 1
        assert mock_hud.call_count == 1
        assert result1.estimated_rent == result2.estimated_rent
