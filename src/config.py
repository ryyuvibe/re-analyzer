from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Database
    database_url: str = "postgresql+asyncpg://reanalyzer:reanalyzer@localhost:5432/reanalyzer"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API Keys
    rentcast_api_key: str = ""
    fred_api_key: str = ""
    census_api_key: str = ""
    walkscore_api_key: str = ""
    greatschools_api_key: str = ""
    anthropic_api_key: str = ""
    hud_api_key: str = ""

    # Rent estimator
    rentcast_monthly_limit: int = 500

    # App
    secret_key: str = "change-me-in-production"
    debug: bool = False
    log_level: str = "INFO"

    # Bonus depreciation thresholds (Congress changes these)
    # Property placed in service after Jan 19, 2025: 100% restored
    bonus_depreciation_rate: dict[int, float] = {
        2022: 1.0,
        2023: 0.80,
        2024: 0.60,
        2025: 1.0,  # Tax Relief for American Families and Workers Act
        2026: 1.0,
        2027: 0.80,
    }


settings = Settings()
