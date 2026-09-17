from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from ..cache import TTLCache
from ..config import get_settings
from ..data_provider import DataUnavailableError, MarketDataProvider, get_data_provider
from ..recommendation_engine import analyze_stock
from ..schemas import ComplianceStatus, DailyPick, DailyRecommendations
from ..universe import get_universe_tickers

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])

_daily_cache: TTLCache[DailyRecommendations] = TTLCache(
    get_settings().daily_recommendations_cache_ttl_seconds
)


def _scan_universe(provider: MarketDataProvider) -> DailyRecommendations:
    settings = get_settings()
    tickers = get_universe_tickers()
    picks: list[DailyPick] = []
    compliant_count = 0

    with ThreadPoolExecutor(max_workers=settings.max_parallel_data_fetches) as executor:
        future_to_ticker = {
            executor.submit(analyze_stock, ticker, provider): ticker for ticker in tickers
        }
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                analysis = future.result()
            except DataUnavailableError as exc:
                logger.warning("skipping %s in daily scan: %s", ticker, exc)
                continue
            except Exception:  # noqa: BLE001
                logger.exception("unexpected error analyzing %s", ticker)
                continue

            if analysis.compliance.status == ComplianceStatus.COMPLIANT:
                compliant_count += 1
                picks.append(
                    DailyPick(
                        ticker=analysis.quote.ticker,
                        name=analysis.quote.name,
                        sector=analysis.quote.sector,
                        price=analysis.quote.price,
                        change_pct=analysis.quote.change_pct,
                        recommendation=analysis.recommendation.label,
                        recommendation_ar=analysis.recommendation.label_ar,
                        composite_score=analysis.recommendation.score.composite_score,
                        compliance_status=analysis.compliance.status,
                    )
                )

    picks.sort(key=lambda pick: pick.composite_score, reverse=True)

    return DailyRecommendations(
        generated_at=datetime.now(timezone.utc).isoformat(),
        universe_size=len(tickers),
        compliant_count=compliant_count,
        picks=picks,
    )


@router.get("/daily", response_model=DailyRecommendations)
def get_daily_recommendations(
    limit: int = Query(default=10, ge=1, le=50),
    refresh: bool = Query(default=False),
) -> DailyRecommendations:
    provider = get_data_provider()
    if refresh:
        _daily_cache.clear()
    full_result = _daily_cache.get_or_set("daily_scan", lambda: _scan_universe(provider))
    return DailyRecommendations(
        generated_at=full_result.generated_at,
        universe_size=full_result.universe_size,
        compliant_count=full_result.compliant_count,
        picks=full_result.picks[:limit],
    )
