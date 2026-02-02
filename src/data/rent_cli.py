"""CLI for testing the tiered rent estimation service.

Usage:
    python -m src.data.rent_cli "123 Main St, Columbus, OH 43215" --beds 3 --baths 1.5 --sqft 1200
    python -m src.data.rent_cli "..." --tier rentcast --serious
    python -m src.data.rent_cli --stats
"""

import argparse
import asyncio
import sys

from src.data.rent_estimator import RentEstimator


def print_estimate(est) -> None:
    print(f"\n{'=' * 60}")
    print(f"  Rent Estimate: {est.address}")
    print(f"{'=' * 60}")
    print(f"  Estimated Rent:   ${est.estimated_rent:,.0f}/mo")
    print(f"  Confidence:       {est.confidence} ({est.confidence_score:.1%})")
    print(f"  Range:            ${est.recommended_range[0]:,.0f} – ${est.recommended_range[1]:,.0f}")
    print(f"  Needs Review:     {'Yes' if est.needs_review else 'No'}")
    print()

    for tr in est.tier_results:
        status = f"${tr.estimate:,.0f}" if tr.estimate else "N/A"
        print(f"  [{tr.tier.upper():>8}]  {status:>10}  ({tr.confidence})")
        print(f"             {tr.reasoning}")
    print()


def print_stats(stats) -> None:
    print(f"\n{'=' * 60}")
    print(f"  Usage Statistics")
    print(f"{'=' * 60}")
    print(f"  Total calls:          {stats.total_calls}")
    print(f"  Cache hits:           {stats.cache_hits}")
    print(f"  Cache hit rate:       {stats.cache_hit_rate:.1%}")
    print(f"  Estimated cost:       ${stats.estimated_cost:.4f}")
    print(f"  RentCast this month:  {stats.rentcast_calls_this_month}")
    print()
    if stats.calls_by_tier:
        print("  Calls by tier:")
        for tier, count in sorted(stats.calls_by_tier.items()):
            print(f"    {tier:>10}: {count}")
    print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Tiered rent estimation CLI")
    parser.add_argument("address", nargs="?", help="Property address")
    parser.add_argument("--beds", type=int, default=3, help="Number of bedrooms (default: 3)")
    parser.add_argument("--baths", type=float, default=1.0, help="Number of bathrooms (default: 1.0)")
    parser.add_argument("--sqft", type=int, default=1200, help="Square footage (default: 1200)")
    parser.add_argument("--type", dest="property_type", default="SFR", help="Property type (default: SFR)")
    parser.add_argument("--tier", choices=["auto", "llm", "hud", "rentcast"], default="auto", help="Estimation tier")
    parser.add_argument("--serious", action="store_true", help="Include RentCast in auto mode")
    parser.add_argument("--stats", action="store_true", help="Show usage statistics")
    parser.add_argument("--db", default="data/rent_cache.db", help="SQLite database path")

    args = parser.parse_args()
    estimator = RentEstimator(db_path=args.db)

    if args.stats:
        stats = estimator.cache.get_usage_stats()
        print_stats(stats)
        return

    if not args.address:
        parser.error("address is required (unless using --stats)")

    result = await estimator.estimate_rent(
        address=args.address,
        beds=args.beds,
        baths=args.baths,
        sqft=args.sqft,
        property_type=args.property_type,
        tier=args.tier,
        serious=args.serious,
    )
    print_estimate(result)


if __name__ == "__main__":
    asyncio.run(main())
