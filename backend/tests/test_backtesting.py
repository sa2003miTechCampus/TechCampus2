import pytest
from tests.conftest import FakeProvider, make_declining_history, make_trending_history

from app import backtesting
from app.backtesting import (
    InsufficientHistoryError,
    compute_technical_score_series,
    run_backtest,
    run_universe_backtest,
    simulate_technical_strategy,
)


def test_uptrend_backtest_enters_and_profits():
    history = make_trending_history(start_price=100, days=1000, daily_drift=0.15, seed=3)
    result = simulate_technical_strategy("UP", history, 10_000.0, 20.0, -20.0, 200)

    assert result.num_trades >= 1
    assert result.total_return_pct > 0
    assert result.final_capital > result.initial_capital
    assert all(trade.hold_days >= 0 for trade in result.trades)


def test_downtrend_backtest_stays_in_cash_and_avoids_loss():
    history = make_declining_history(start_price=500, days=1000, daily_drift=-0.15, seed=5)
    result = simulate_technical_strategy("DOWN", history, 10_000.0, 20.0, -20.0, 200)

    assert result.num_trades == 0
    assert result.total_return_pct == 0.0
    assert result.final_capital == result.initial_capital
    assert result.buy_and_hold_return_pct < 0


def test_insufficient_history_raises():
    history = make_trending_history(days=50)
    with pytest.raises(InsufficientHistoryError):
        simulate_technical_strategy("SHORT", history, 10_000.0, 20.0, -20.0, 200)


def test_no_lookahead_entry_price_is_next_day_open():
    history = make_trending_history(start_price=100, days=1000, daily_drift=0.15, seed=3)
    score_series = compute_technical_score_series(history).dropna()
    result = simulate_technical_strategy("UP", history, 10_000.0, 20.0, -20.0, 200)

    assert result.trades, "expected at least one trade to validate execution timing"
    first_trade = result.trades[0]
    entry_ts = next(idx for idx in history.index if str(idx.date()) == first_trade.entry_date)
    assert float(history.loc[entry_ts, "Open"]) == pytest.approx(first_trade.entry_price)

    dates = score_series.index.tolist()
    entry_pos = dates.index(entry_ts)
    signal_date = dates[entry_pos - 1]
    assert score_series.loc[signal_date] >= 20.0


def test_flat_price_stretch_does_not_nan_out_score():
    history = make_declining_history(start_price=57.0, days=1200, seed=2)
    assert history["Close"].min() == pytest.approx(1.0)

    score_series = compute_technical_score_series(history)
    scored_after_warmup = score_series.iloc[250:]
    assert scored_after_warmup.notna().sum() > len(scored_after_warmup) * 0.9

    result = simulate_technical_strategy("FLAT", history, 10_000.0, 20.0, -20.0, 200)
    assert result.num_trades >= 0


def test_max_drawdown_is_never_positive():
    history = make_trending_history(start_price=100, days=1000, daily_drift=0.15, seed=3)
    result = simulate_technical_strategy("UP", history, 10_000.0, 20.0, -20.0, 200)
    assert result.max_drawdown_pct <= 0.0


def test_run_backtest_uses_extended_history_period(compliant_quote, compliant_fundamentals):
    history = make_trending_history(start_price=100, days=1000, daily_drift=0.15, seed=3)
    provider = FakeProvider(
        quotes={"HALAL": compliant_quote},
        fundamentals={"HALAL": compliant_fundamentals},
        histories={"HALAL": history},
    )
    result = run_backtest("halal", provider)
    assert result.ticker == "HALAL"


def test_run_universe_backtest_aggregates(monkeypatch):
    uptrend = make_trending_history(start_price=100, days=1000, daily_drift=0.15, seed=3)
    downtrend = make_declining_history(start_price=500, days=1000, daily_drift=-0.15, seed=5)
    provider = FakeProvider(histories={"UP": uptrend, "DOWN": downtrend})

    monkeypatch.setattr(backtesting, "get_universe_tickers", lambda: ["UP", "DOWN", "MISSING"])

    summary = run_universe_backtest(provider, limit=3)

    assert summary.tested_count == 2
    assert summary.failed_count == 1
    tickers = {entry.ticker for entry in summary.results}
    assert tickers == {"UP", "DOWN"}
