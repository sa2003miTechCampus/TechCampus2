from __future__ import annotations

import pandas as pd

from .schemas import TechnicalIndicators


def _sma(series: pd.Series, window: int) -> float | None:
    if len(series) < window:
        return None
    return float(series.rolling(window=window).mean().iloc[-1])


def _ema_series(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _ema(series: pd.Series, span: int) -> float | None:
    if len(series) < span:
        return None
    return float(_ema_series(series, span).iloc[-1])


def _rsi(series: pd.Series, period: int = 14) -> float | None:
    if len(series) < period + 1:
        return None
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()
    last_avg_loss = avg_loss.iloc[-1]
    last_avg_gain = avg_gain.iloc[-1]
    if pd.isna(last_avg_gain) or pd.isna(last_avg_loss):
        return None
    if last_avg_loss == 0:
        return 100.0
    rs = last_avg_gain / last_avg_loss
    return float(100 - (100 / (1 + rs)))


def _macd(series: pd.Series) -> tuple[float | None, float | None, float | None]:
    if len(series) < 26:
        return None, None, None
    ema12 = _ema_series(series, 12)
    ema26 = _ema_series(series, 26)
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    return float(macd_line.iloc[-1]), float(signal_line.iloc[-1]), float(histogram.iloc[-1])


def _bollinger_bands(
    series: pd.Series, window: int = 20, num_std: float = 2.0
) -> tuple[float | None, float | None, float | None]:
    if len(series) < window:
        return None, None, None
    rolling_mean = series.rolling(window=window).mean()
    rolling_std = series.rolling(window=window).std()
    mid = float(rolling_mean.iloc[-1])
    upper = float(mid + num_std * rolling_std.iloc[-1])
    lower = float(mid - num_std * rolling_std.iloc[-1])
    return upper, lower, mid


def _volume_trend_pct(volume: pd.Series, short_window: int = 10, long_window: int = 50) -> float | None:
    if len(volume) < long_window:
        return None
    recent_avg = volume.tail(short_window).mean()
    baseline_avg = volume.tail(long_window).mean()
    if baseline_avg == 0 or pd.isna(baseline_avg):
        return None
    return float((recent_avg - baseline_avg) / baseline_avg * 100)


def compute_technical_indicators(history: pd.DataFrame) -> TechnicalIndicators:
    close = history["Close"].dropna()
    last_price = float(close.iloc[-1])

    macd_line, macd_signal, macd_hist = _macd(close)
    bb_upper, bb_lower, bb_mid = _bollinger_bands(close)

    volume = history["Volume"].dropna() if "Volume" in history else pd.Series(dtype=float)

    lookback = close.tail(252)

    return TechnicalIndicators(
        last_price=last_price,
        sma_20=_sma(close, 20),
        sma_50=_sma(close, 50),
        sma_200=_sma(close, 200),
        ema_12=_ema(close, 12),
        ema_26=_ema(close, 26),
        rsi_14=_rsi(close, 14),
        macd=macd_line,
        macd_signal=macd_signal,
        macd_histogram=macd_hist,
        bollinger_upper=bb_upper,
        bollinger_lower=bb_lower,
        bollinger_mid=bb_mid,
        week52_high=float(lookback.max()) if not lookback.empty else None,
        week52_low=float(lookback.min()) if not lookback.empty else None,
        volume_trend_pct=_volume_trend_pct(volume) if not volume.empty else None,
    )
