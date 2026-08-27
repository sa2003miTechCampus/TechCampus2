from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.data_provider import DataUnavailableError, FundamentalsData, QuoteData


def make_trending_history(
    start_price: float = 100.0, days: int = 260, daily_drift: float = 0.8, seed: int = 7
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    noise = rng.normal(loc=0.0, scale=0.25, size=days)
    prices = start_price + np.cumsum(np.full(days, daily_drift) + noise)
    prices = np.maximum(prices, 1.0)
    dates = pd.date_range(end=pd.Timestamp.today(), periods=days, freq="D")
    volume = rng.integers(low=1_000_000, high=5_000_000, size=days).astype(float)
    return pd.DataFrame(
        {
            "Open": prices,
            "High": prices * 1.01,
            "Low": prices * 0.99,
            "Close": prices,
            "Volume": volume,
        },
        index=dates,
    )


def make_declining_history(
    start_price: float = 200.0, days: int = 260, daily_drift: float = -0.3, seed: int = 11
) -> pd.DataFrame:
    return make_trending_history(start_price=start_price, days=days, daily_drift=daily_drift, seed=seed)


class FakeProvider:
    def __init__(
        self,
        quotes: dict[str, QuoteData] | None = None,
        fundamentals: dict[str, FundamentalsData] | None = None,
        histories: dict[str, pd.DataFrame] | None = None,
    ) -> None:
        self.quotes = quotes or {}
        self.fundamentals = fundamentals or {}
        self.histories = histories or {}

    def get_quote(self, ticker: str) -> QuoteData:
        if ticker not in self.quotes:
            raise DataUnavailableError(ticker, "no fake quote configured")
        return self.quotes[ticker]

    def get_fundamentals(self, ticker: str) -> FundamentalsData:
        if ticker not in self.fundamentals:
            raise DataUnavailableError(ticker, "no fake fundamentals configured")
        return self.fundamentals[ticker]

    def get_price_history(self, ticker: str) -> pd.DataFrame:
        if ticker not in self.histories:
            raise DataUnavailableError(ticker, "no fake history configured")
        return self.histories[ticker]


@pytest.fixture
def compliant_quote() -> QuoteData:
    return QuoteData(
        ticker="HALAL",
        name="Halal Tech Co",
        sector="Technology",
        industry="Software - Application",
        currency="USD",
        price=150.0,
        previous_close=145.0,
        market_cap=100_000_000_000.0,
        trailing_pe=22.0,
        forward_pe=20.0,
        profit_margin=0.18,
        revenue_growth=0.15,
        fifty_two_week_high=160.0,
        fifty_two_week_low=90.0,
    )


@pytest.fixture
def compliant_fundamentals() -> FundamentalsData:
    return FundamentalsData(
        total_debt=10_000_000_000.0,
        total_cash_and_securities=15_000_000_000.0,
        net_receivables=8_000_000_000.0,
        total_revenue=50_000_000_000.0,
        impure_income=100_000_000.0,
        data_complete=True,
    )


@pytest.fixture
def bank_quote() -> QuoteData:
    return QuoteData(
        ticker="BANK",
        name="Conventional Bank Corp",
        sector="Financial Services",
        industry="Banks - Regional",
        currency="USD",
        price=50.0,
        previous_close=49.0,
        market_cap=20_000_000_000.0,
        trailing_pe=10.0,
        forward_pe=9.0,
        profit_margin=0.25,
        revenue_growth=0.05,
        fifty_two_week_high=55.0,
        fifty_two_week_low=40.0,
    )


@pytest.fixture
def highly_leveraged_quote() -> QuoteData:
    return QuoteData(
        ticker="DEBTCO",
        name="Debt Heavy Corp",
        sector="Industrials",
        industry="Airlines",
        currency="USD",
        price=30.0,
        previous_close=31.0,
        market_cap=5_000_000_000.0,
        trailing_pe=15.0,
        forward_pe=14.0,
        profit_margin=0.05,
        revenue_growth=0.02,
        fifty_two_week_high=40.0,
        fifty_two_week_low=20.0,
    )


@pytest.fixture
def highly_leveraged_fundamentals() -> FundamentalsData:
    return FundamentalsData(
        total_debt=4_000_000_000.0,
        total_cash_and_securities=500_000_000.0,
        net_receivables=200_000_000.0,
        total_revenue=6_000_000_000.0,
        impure_income=None,
        data_complete=True,
    )
