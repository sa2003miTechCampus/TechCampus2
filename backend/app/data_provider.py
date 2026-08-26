from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import pandas as pd
import yfinance as yf

from .cache import TTLCache
from .config import get_settings

logger = logging.getLogger(__name__)


class DataUnavailableError(Exception):
    def __init__(self, ticker: str, reason: str) -> None:
        self.ticker = ticker
        self.reason = reason
        super().__init__(f"Data unavailable for {ticker}: {reason}")


@dataclass(frozen=True)
class QuoteData:
    ticker: str
    name: str
    sector: str | None
    industry: str | None
    currency: str
    price: float
    previous_close: float | None
    market_cap: float | None
    trailing_pe: float | None
    forward_pe: float | None
    profit_margin: float | None
    revenue_growth: float | None
    fifty_two_week_high: float | None
    fifty_two_week_low: float | None


@dataclass(frozen=True)
class FundamentalsData:
    total_debt: float | None
    total_cash_and_securities: float | None
    net_receivables: float | None
    total_revenue: float | None
    impure_income: float | None
    data_complete: bool


class MarketDataProvider(Protocol):
    def get_quote(self, ticker: str) -> QuoteData: ...

    def get_fundamentals(self, ticker: str) -> FundamentalsData: ...

    def get_price_history(self, ticker: str) -> pd.DataFrame: ...


def _find_row_value(df: pd.DataFrame, candidates: list[str]) -> float | None:
    if df is None or df.empty:
        return None
    normalized_index = {str(idx).strip().lower(): idx for idx in df.index}
    for candidate in candidates:
        key = candidate.strip().lower()
        if key in normalized_index:
            series = df.loc[normalized_index[key]]
            for value in series:
                if pd.notna(value):
                    return float(value)
    return None


class YFinanceProvider:
    def __init__(self) -> None:
        settings = get_settings()
        self._quote_cache: TTLCache[QuoteData] = TTLCache(settings.quote_cache_ttl_seconds)
        self._fundamentals_cache: TTLCache[FundamentalsData] = TTLCache(
            settings.fundamentals_cache_ttl_seconds
        )
        self._history_cache: TTLCache[pd.DataFrame] = TTLCache(settings.history_cache_ttl_seconds)

    def get_quote(self, ticker: str) -> QuoteData:
        return self._quote_cache.get_or_set(ticker, lambda: self._fetch_quote(ticker))

    def get_fundamentals(self, ticker: str) -> FundamentalsData:
        return self._fundamentals_cache.get_or_set(ticker, lambda: self._fetch_fundamentals(ticker))

    def get_price_history(self, ticker: str) -> pd.DataFrame:
        return self._history_cache.get_or_set(ticker, lambda: self._fetch_history(ticker))

    def _fetch_quote(self, ticker: str) -> QuoteData:
        try:
            yf_ticker = yf.Ticker(ticker)
            info = yf_ticker.info or {}
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailableError(ticker, f"failed to fetch info: {exc}") from exc

        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            price = self._fetch_last_close(ticker)
            if price is None:
                raise DataUnavailableError(ticker, "no quote data returned by provider")
        else:
            price = info.get("currentPrice") or info.get("regularMarketPrice")

        name = info.get("longName") or info.get("shortName") or ticker
        market_cap = info.get("marketCap")

        return QuoteData(
            ticker=ticker,
            name=name,
            sector=info.get("sector"),
            industry=info.get("industry"),
            currency=info.get("currency") or "USD",
            price=float(price),
            previous_close=info.get("previousClose"),
            market_cap=float(market_cap) if market_cap else None,
            trailing_pe=info.get("trailingPE"),
            forward_pe=info.get("forwardPE"),
            profit_margin=info.get("profitMargins"),
            revenue_growth=info.get("revenueGrowth"),
            fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
            fifty_two_week_low=info.get("fiftyTwoWeekLow"),
        )

    def _fetch_last_close(self, ticker: str) -> float | None:
        history = self._fetch_history(ticker)
        if history is None or history.empty:
            return None
        return float(history["Close"].iloc[-1])

    def _fetch_fundamentals(self, ticker: str) -> FundamentalsData:
        try:
            yf_ticker = yf.Ticker(ticker)
            balance_sheet = yf_ticker.balance_sheet
            income_stmt = yf_ticker.income_stmt
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailableError(ticker, f"failed to fetch financial statements: {exc}") from exc

        total_debt = _find_row_value(balance_sheet, ["Total Debt", "Net Debt"])
        cash = _find_row_value(
            balance_sheet,
            ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
        )
        short_term_investments = _find_row_value(
            balance_sheet, ["Other Short Term Investments", "Short Term Investments"]
        )
        receivables = _find_row_value(
            balance_sheet, ["Receivables", "Accounts Receivable", "Net Receivables"]
        )
        total_revenue = _find_row_value(income_stmt, ["Total Revenue", "Operating Revenue"])
        interest_income = _find_row_value(income_stmt, ["Interest Income", "Interest Income Non Operating"])

        cash_and_securities = None
        if cash is not None or short_term_investments is not None:
            cash_and_securities = (cash or 0.0) + (short_term_investments or 0.0)

        data_complete = all(
            value is not None for value in (total_debt, cash_and_securities, receivables, total_revenue)
        )

        return FundamentalsData(
            total_debt=total_debt,
            total_cash_and_securities=cash_and_securities,
            net_receivables=receivables,
            total_revenue=total_revenue,
            impure_income=interest_income,
            data_complete=data_complete,
        )

    def _fetch_history(self, ticker: str) -> pd.DataFrame:
        settings = get_settings()
        try:
            yf_ticker = yf.Ticker(ticker)
            history = yf_ticker.history(
                period=settings.history_period, interval=settings.history_interval, auto_adjust=True
            )
        except Exception as exc:  # noqa: BLE001
            raise DataUnavailableError(ticker, f"failed to fetch price history: {exc}") from exc
        if history is None or history.empty:
            raise DataUnavailableError(ticker, "no price history returned by provider")
        return history


_provider: MarketDataProvider | None = None


def get_data_provider() -> MarketDataProvider:
    global _provider
    if _provider is None:
        _provider = YFinanceProvider()
    return _provider


def set_data_provider(provider: MarketDataProvider) -> None:
    global _provider
    _provider = provider
