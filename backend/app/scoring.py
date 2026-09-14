from __future__ import annotations

from .config import get_settings
from .schemas import FundamentalMetrics, ScoreBreakdown, TechnicalIndicators

# Shared with app/backtesting.py so the historical simulation scores each day using the
# exact same formula as the live technical score - a backtest that drifted from production
# logic would validate nothing.
TREND_WEIGHT = 0.40
RSI_WEIGHT = 0.20
MACD_WEIGHT = 0.15
BOLLINGER_WEIGHT = 0.15
WEEK52_WEIGHT = 0.10


def _clip(value: float, low: float = -100.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _weighted_average(components: list[tuple[float, float]]) -> float | None:
    if not components:
        return None
    total_weight = sum(weight for _, weight in components)
    if total_weight == 0:
        return None
    return sum(value * weight for value, weight in components) / total_weight


def compute_technical_score(indicators: TechnicalIndicators) -> float:
    components: list[tuple[float, float]] = []

    trend_signals = []
    if indicators.sma_50 is not None:
        trend_signals.append(1.0 if indicators.last_price > indicators.sma_50 else -1.0)
    if indicators.sma_200 is not None:
        trend_signals.append(1.0 if indicators.last_price > indicators.sma_200 else -1.0)
    if indicators.sma_50 is not None and indicators.sma_200 is not None:
        trend_signals.append(1.0 if indicators.sma_50 > indicators.sma_200 else -1.0)
    if trend_signals:
        components.append((sum(trend_signals) / len(trend_signals) * 100, TREND_WEIGHT))

    if indicators.rsi_14 is not None:
        rsi_score = _clip((50 - indicators.rsi_14) * 2.5)
        components.append((rsi_score, RSI_WEIGHT))

    if indicators.macd_histogram is not None and indicators.last_price:
        macd_score = _clip((indicators.macd_histogram / indicators.last_price) * 1000)
        components.append((macd_score, MACD_WEIGHT))

    if (
        indicators.bollinger_upper is not None
        and indicators.bollinger_lower is not None
        and indicators.bollinger_upper != indicators.bollinger_lower
    ):
        band_range = indicators.bollinger_upper - indicators.bollinger_lower
        position = (indicators.last_price - indicators.bollinger_lower) / band_range
        bollinger_score = _clip((0.5 - position) * 200)
        components.append((bollinger_score, BOLLINGER_WEIGHT))

    if (
        indicators.week52_high is not None
        and indicators.week52_low is not None
        and indicators.week52_high != indicators.week52_low
    ):
        proximity = (indicators.last_price - indicators.week52_low) / (
            indicators.week52_high - indicators.week52_low
        )
        proximity_score = _clip((proximity - 0.5) * 100)
        components.append((proximity_score, WEEK52_WEIGHT))

    score = _weighted_average(components)
    return round(_clip(score) if score is not None else 0.0, 2)


def compute_fundamental_score(fundamentals: FundamentalMetrics) -> float:
    components: list[tuple[float, float]] = []

    if fundamentals.trailing_pe is not None and fundamentals.trailing_pe > 0:
        components.append((_clip((25 - fundamentals.trailing_pe) * 4), 0.4))

    if fundamentals.revenue_growth is not None:
        components.append((_clip(fundamentals.revenue_growth * 400), 0.3))

    if fundamentals.profit_margin is not None:
        components.append((_clip(fundamentals.profit_margin * 400), 0.3))

    score = _weighted_average(components)
    return round(_clip(score) if score is not None else 0.0, 2)


def build_score_breakdown(
    indicators: TechnicalIndicators, fundamentals: FundamentalMetrics
) -> ScoreBreakdown:
    settings = get_settings()
    technical_score = compute_technical_score(indicators)
    fundamental_score = compute_fundamental_score(fundamentals)
    composite_score = round(
        _clip(
            technical_score * settings.technical_weight
            + fundamental_score * settings.fundamental_weight
        ),
        2,
    )
    return ScoreBreakdown(
        technical_score=technical_score,
        fundamental_score=fundamental_score,
        composite_score=composite_score,
        technical_weight=settings.technical_weight,
        fundamental_weight=settings.fundamental_weight,
    )
