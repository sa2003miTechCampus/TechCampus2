"""Historical simulation of the technical scoring strategy.

Only the technical component of the recommendation engine is backtested here.
Yahoo's free balance-sheet/income-statement endpoints only return a handful of
recent fiscal periods, not point-in-time snapshots aligned to each historical
trading day, so the fundamental score cannot be reconstructed honestly for
past dates without look-ahead bias. Excluding it is a deliberate choice to
avoid testing a strategy that isn't the one actually deployed.

Execution model: a signal computed from data available through day t is
never filled at day t's price - it fills at day t+1's opening price, the
earliest a real order could realistically execute. No shorting, no leverage,
a single all-in/all-out position at a time. Transaction costs, spreads and
taxes are not modeled, so real results would be somewhat worse than shown
here.
"""

from __future__ import annotations

import pandas as pd

from .config import get_settings
from .data_provider import DataUnavailableError, MarketDataProvider
from .scoring import BOLLINGER_WEIGHT, MACD_WEIGHT, RSI_WEIGHT, TREND_WEIGHT, WEEK52_WEIGHT
from .schemas import (
    BacktestResult,
    BacktestTrade,
    EquityPoint,
    UniverseBacktestEntry,
    UniverseBacktestSummary,
)
from .universe import get_universe_tickers

METHODOLOGY_NOTE_AR = (
    "هذا اختبار خلفي (Backtesting) للمكوّن الفني فقط من محرك التوصيات (وليس المكوّن "
    "الأساسي/المالي)، لأن البيانات المالية التاريخية المتاحة مجاناً لا تسمح بإعادة بناء "
    "القيم الفعلية في كل تاريخ دون تحيّز معرفة مستقبلية. الصفقات تُنفَّذ بسعر افتتاح اليوم "
    "التالي لصدور الإشارة (لا تنفيذ فوري)، بدون احتساب عمولات أو فروقات سعرية أو ضرائب، "
    "وبمركز واحد فقط (شراء بالكامل / بيع بالكامل) دون رافعة مالية أو بيع على المكشوف. "
    "الأداء التاريخي، حتى لو كان إيجابياً، لا يضمن نتائج مستقبلية مماثلة."
)


class InsufficientHistoryError(Exception):
    def __init__(self, ticker: str, available_days: int, required_days: int) -> None:
        self.ticker = ticker
        self.available_days = available_days
        self.required_days = required_days
        super().__init__(
            f"{ticker}: only {available_days} trading days available, need at least {required_days}"
        )


def _rsi_series(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return rsi.mask(avg_loss == 0, 100.0).astype(float)


def _macd_series(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line


def _bollinger_series(close: pd.Series, window: int = 20, num_std: float = 2.0) -> tuple[pd.Series, pd.Series]:
    mid = close.rolling(window=window).mean()
    std = close.rolling(window=window).std()
    return mid + num_std * std, mid - num_std * std


def compute_technical_score_series(history: pd.DataFrame) -> pd.Series:
    close = history["Close"]

    sma_50 = close.rolling(window=50).mean()
    sma_200 = close.rolling(window=200).mean()
    trend1 = (close > sma_50).astype(float) * 2 - 1
    trend2 = (close > sma_200).astype(float) * 2 - 1
    trend3 = (sma_50 > sma_200).astype(float) * 2 - 1
    trend_component = ((trend1 + trend2 + trend3) / 3 * 100).where(sma_50.notna() & sma_200.notna())

    rsi = _rsi_series(close)
    rsi_component = ((50 - rsi) * 2.5).clip(-100, 100)

    _, _, histogram = _macd_series(close)
    macd_component = ((histogram / close) * 1000).clip(-100, 100)

    # A single missing component (e.g. zero-volatility Bollinger width during a flat
    # stretch) must not NaN out the whole day's score via addition - fall back to a
    # neutral 0 contribution instead, mirroring how the live per-point scorer simply
    # omits an unavailable component rather than invalidating the composite.
    upper, lower = _bollinger_series(close)
    band_range = upper - lower
    position = (close - lower) / band_range.replace(0, float("nan"))
    bollinger_component = ((0.5 - position) * 200).clip(-100, 100).fillna(0.0)

    high_52w = close.rolling(window=252, min_periods=1).max()
    low_52w = close.rolling(window=252, min_periods=1).min()
    range_52w = high_52w - low_52w
    proximity = (close - low_52w) / range_52w.replace(0, float("nan"))
    week52_component = ((proximity - 0.5) * 100).clip(-100, 100).fillna(0.0)

    score = (
        TREND_WEIGHT * trend_component
        + RSI_WEIGHT * rsi_component
        + MACD_WEIGHT * macd_component
        + BOLLINGER_WEIGHT * bollinger_component
        + WEEK52_WEIGHT * week52_component
    )
    return score.clip(-100, 100)


def _max_drawdown_pct(values: list[float]) -> float:
    running_max = float("-inf")
    max_drawdown = 0.0
    for value in values:
        running_max = max(running_max, value)
        if running_max > 0:
            drawdown = (value - running_max) / running_max
            max_drawdown = min(max_drawdown, drawdown)
    return round(max_drawdown * 100, 2)


def simulate_technical_strategy(
    ticker: str,
    history: pd.DataFrame,
    initial_capital: float,
    buy_threshold: float,
    sell_threshold: float,
    min_scored_days: int,
) -> BacktestResult:
    score_series = compute_technical_score_series(history).dropna()
    if len(score_series) < min_scored_days:
        raise InsufficientHistoryError(ticker, len(score_series), min_scored_days)

    dates = score_series.index.tolist()
    n = len(dates)

    cash = initial_capital
    shares = 0.0
    position_open = False
    entry_date = None
    entry_price = None

    trades: list[BacktestTrade] = []
    equity_curve: list[EquityPoint] = []

    for i in range(n):
        date = dates[i]
        score = float(score_series.iloc[i])
        close_price = float(history.loc[date, "Close"])

        current_equity = cash if not position_open else shares * close_price
        equity_curve.append(EquityPoint(date=str(date.date()), value=round(current_equity, 2)))

        has_next_day = i + 1 < n
        if not has_next_day:
            continue

        next_date = dates[i + 1]
        next_open = float(history.loc[next_date, "Open"])

        if not position_open and score >= buy_threshold:
            shares = cash / next_open
            cash = 0.0
            position_open = True
            entry_date = next_date
            entry_price = next_open
        elif position_open and score <= sell_threshold:
            return_pct = (next_open - entry_price) / entry_price * 100
            trades.append(
                BacktestTrade(
                    entry_date=str(entry_date.date()),
                    exit_date=str(next_date.date()),
                    entry_price=round(entry_price, 4),
                    exit_price=round(next_open, 4),
                    return_pct=round(return_pct, 2),
                    hold_days=(next_date - entry_date).days,
                    still_open=False,
                )
            )
            cash = shares * next_open
            shares = 0.0
            position_open = False
            entry_date = None
            entry_price = None

    final_date = dates[-1]
    final_close = float(history.loc[final_date, "Close"])
    if position_open:
        final_capital = shares * final_close
        trades.append(
            BacktestTrade(
                entry_date=str(entry_date.date()),
                exit_date=None,
                entry_price=round(entry_price, 4),
                exit_price=round(final_close, 4),
                return_pct=round((final_close - entry_price) / entry_price * 100, 2),
                hold_days=(final_date - entry_date).days,
                still_open=True,
            )
        )
        equity_curve[-1] = EquityPoint(date=str(final_date.date()), value=round(final_capital, 2))
    else:
        final_capital = cash

    start_close = float(history.loc[dates[0], "Close"])
    buy_and_hold_return_pct = round((final_close - start_close) / start_close * 100, 2)

    days_elapsed = (final_date - dates[0]).days
    years = days_elapsed / 365.25
    if years > 0 and final_capital > 0:
        cagr_pct = round(((final_capital / initial_capital) ** (1 / years) - 1) * 100, 2)
    else:
        cagr_pct = 0.0

    win_rate_pct = (
        round(sum(1 for t in trades if t.return_pct > 0) / len(trades) * 100, 2) if trades else None
    )

    return BacktestResult(
        ticker=ticker,
        start_date=str(dates[0].date()),
        end_date=str(final_date.date()),
        initial_capital=initial_capital,
        final_capital=round(final_capital, 2),
        total_return_pct=round((final_capital - initial_capital) / initial_capital * 100, 2),
        cagr_pct=cagr_pct,
        max_drawdown_pct=_max_drawdown_pct([point.value for point in equity_curve]),
        num_trades=len(trades),
        win_rate_pct=win_rate_pct,
        buy_and_hold_return_pct=buy_and_hold_return_pct,
        trades=trades,
        equity_curve=equity_curve,
        methodology_note_ar=METHODOLOGY_NOTE_AR,
    )


def run_backtest(
    ticker: str,
    provider: MarketDataProvider,
    initial_capital: float = 10_000.0,
    buy_threshold: float | None = None,
    sell_threshold: float | None = None,
) -> BacktestResult:
    settings = get_settings()
    ticker = ticker.strip().upper()
    history = provider.get_price_history(ticker, period=settings.backtest_history_period)
    return simulate_technical_strategy(
        ticker=ticker,
        history=history,
        initial_capital=initial_capital,
        buy_threshold=buy_threshold if buy_threshold is not None else settings.buy_threshold,
        sell_threshold=sell_threshold if sell_threshold is not None else settings.sell_threshold,
        min_scored_days=settings.backtest_warmup_days,
    )


def run_universe_backtest(
    provider: MarketDataProvider, limit: int | None = None
) -> UniverseBacktestSummary:
    settings = get_settings()
    tickers = get_universe_tickers()[: limit or settings.backtest_max_universe_tickers]

    entries: list[UniverseBacktestEntry] = []
    failed_count = 0

    for ticker in tickers:
        try:
            result = run_backtest(ticker, provider)
        except (DataUnavailableError, InsufficientHistoryError):
            failed_count += 1
            continue
        entries.append(
            UniverseBacktestEntry(
                ticker=result.ticker,
                total_return_pct=result.total_return_pct,
                buy_and_hold_return_pct=result.buy_and_hold_return_pct,
                num_trades=result.num_trades,
                win_rate_pct=result.win_rate_pct,
                beat_buy_and_hold=result.total_return_pct > result.buy_and_hold_return_pct,
            )
        )

    tested_count = len(entries)
    avg_strategy = round(sum(e.total_return_pct for e in entries) / tested_count, 2) if tested_count else 0.0
    avg_buy_hold = (
        round(sum(e.buy_and_hold_return_pct for e in entries) / tested_count, 2) if tested_count else 0.0
    )
    pct_beating = (
        round(sum(1 for e in entries if e.beat_buy_and_hold) / tested_count * 100, 2) if tested_count else 0.0
    )

    return UniverseBacktestSummary(
        tested_count=tested_count,
        failed_count=failed_count,
        average_strategy_return_pct=avg_strategy,
        average_buy_and_hold_return_pct=avg_buy_hold,
        pct_beating_buy_and_hold=pct_beating,
        results=sorted(entries, key=lambda e: e.total_return_pct, reverse=True),
        methodology_note_ar=METHODOLOGY_NOTE_AR,
    )
