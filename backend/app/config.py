from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HALAL_", env_file=".env", extra="ignore")

    app_name: str = "Halal Stocks Analyzer"
    cors_origins: list[str] = ["*"]

    quote_cache_ttl_seconds: int = 300
    fundamentals_cache_ttl_seconds: int = 3600
    history_cache_ttl_seconds: int = 900
    daily_recommendations_cache_ttl_seconds: int = 1800

    history_period: str = "1y"
    history_interval: str = "1d"

    screening_max_debt_to_market_cap: float = 0.33
    screening_max_cash_securities_to_market_cap: float = 0.33
    screening_max_receivables_to_market_cap: float = 0.33
    screening_max_impure_income_to_revenue: float = 0.05

    technical_weight: float = 0.6
    fundamental_weight: float = 0.4

    max_parallel_data_fetches: int = 10

    strong_buy_threshold: float = 60.0
    buy_threshold: float = 20.0
    sell_threshold: float = -20.0
    strong_sell_threshold: float = -60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
