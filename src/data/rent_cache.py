"""SQLite-backed cache and usage tracking for the rent estimation service."""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from src.models.rent_estimate import UsageStats

logger = logging.getLogger(__name__)


class RentCache:
    def __init__(self, db_path: str = "data/rent_cache.db"):
        self.db_path = db_path
        self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS rent_cache (
                    cache_key TEXT PRIMARY KEY,
                    tier TEXT,
                    address TEXT,
                    estimate_json TEXT,
                    created_at TIMESTAMP,
                    expires_at TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS api_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tier TEXT,
                    address TEXT,
                    called_at TIMESTAMP,
                    cost_estimate REAL,
                    cache_hit BOOLEAN
                );

                CREATE TABLE IF NOT EXISTS hud_fmr_cache (
                    entity_id TEXT PRIMARY KEY,
                    fmr_json TEXT,
                    fetched_at TIMESTAMP
                );
            """)

    def get_cached(self, key: str, tier: str) -> dict | None:
        """Return cached estimate data or None if missing/expired."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT estimate_json FROM rent_cache "
                "WHERE cache_key = ? AND tier = ? AND expires_at > ?",
                (key, tier, now),
            ).fetchone()
        if row:
            return json.loads(row["estimate_json"])
        return None

    def set_cached(self, key: str, tier: str, address: str, data: dict, ttl_days: int) -> None:
        """Store an estimate in the cache."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=ttl_days)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO rent_cache "
                "(cache_key, tier, address, estimate_json, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (key, tier, address, json.dumps(data), now.isoformat(), expires.isoformat()),
            )

    def get_hud_cached(self, entity_id: str, max_age_days: int = 180) -> dict | None:
        """Return cached HUD FMR data or None if missing/stale."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT fmr_json FROM hud_fmr_cache "
                "WHERE entity_id = ? AND fetched_at > ?",
                (entity_id, cutoff),
            ).fetchone()
        if row:
            return json.loads(row["fmr_json"])
        return None

    def set_hud_cached(self, entity_id: str, data: dict) -> None:
        """Store HUD FMR data in cache."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO hud_fmr_cache "
                "(entity_id, fmr_json, fetched_at) VALUES (?, ?, ?)",
                (entity_id, json.dumps(data), now),
            )

    def log_usage(self, tier: str, address: str, cost: float, cache_hit: bool) -> None:
        """Record an API usage event."""
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO api_usage (tier, address, called_at, cost_estimate, cache_hit) "
                "VALUES (?, ?, ?, ?, ?)",
                (tier, address, now, cost, cache_hit),
            )

    def get_rentcast_calls_this_month(self) -> int:
        """Count RentCast API calls (non-cache-hit) in the current calendar month."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM api_usage "
                "WHERE tier = 'rentcast' AND cache_hit = 0 AND called_at >= ?",
                (month_start,),
            ).fetchone()
        return row["cnt"] if row else 0

    def get_usage_stats(self) -> UsageStats:
        """Aggregate usage statistics across all tiers."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) as cnt FROM api_usage").fetchone()["cnt"]
            hits = conn.execute(
                "SELECT COUNT(*) as cnt FROM api_usage WHERE cache_hit = 1"
            ).fetchone()["cnt"]
            cost = conn.execute(
                "SELECT COALESCE(SUM(cost_estimate), 0) as total FROM api_usage WHERE cache_hit = 0"
            ).fetchone()["total"]

            rows = conn.execute(
                "SELECT tier, COUNT(*) as cnt FROM api_usage GROUP BY tier"
            ).fetchall()
            calls_by_tier = {row["tier"]: row["cnt"] for row in rows}

        return UsageStats(
            total_calls=total,
            cache_hits=hits,
            cache_hit_rate=hits / total if total > 0 else 0.0,
            calls_by_tier=calls_by_tier,
            estimated_cost=cost,
            rentcast_calls_this_month=self.get_rentcast_calls_this_month(),
        )
