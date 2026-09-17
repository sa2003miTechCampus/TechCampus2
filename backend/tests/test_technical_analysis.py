from tests.conftest import make_declining_history, make_trending_history

from app.technical_analysis import compute_technical_indicators


def test_uptrend_indicators_are_bullish():
    history = make_trending_history()
    indicators = compute_technical_indicators(history)

    assert indicators.sma_20 is not None
    assert indicators.sma_50 is not None
    assert indicators.last_price > indicators.sma_50 > indicators.sma_200
    assert indicators.rsi_14 is not None and indicators.rsi_14 > 50
    assert indicators.macd is not None and indicators.macd > 0


def test_downtrend_indicators_are_bearish():
    history = make_declining_history()
    indicators = compute_technical_indicators(history)

    assert indicators.last_price < indicators.sma_50 < indicators.sma_200
    assert indicators.rsi_14 is not None and indicators.rsi_14 < 50


def test_bollinger_bands_ordering():
    history = make_trending_history()
    indicators = compute_technical_indicators(history)
    assert indicators.bollinger_lower < indicators.bollinger_mid < indicators.bollinger_upper


def test_52_week_range_contains_last_price():
    history = make_trending_history()
    indicators = compute_technical_indicators(history)
    assert indicators.week52_low <= indicators.last_price <= indicators.week52_high


def test_short_history_returns_none_for_long_window_indicators():
    history = make_trending_history(days=30)
    indicators = compute_technical_indicators(history)
    assert indicators.sma_200 is None
    assert indicators.sma_20 is not None
