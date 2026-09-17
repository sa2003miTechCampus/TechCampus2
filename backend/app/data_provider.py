from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol, TypeVar

import pandas as pd
import yfinance as yf

from .cache import TTLCache
from .config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class _RateLimiter:
    """Spaces out requests to Yahoo Finance to avoid tripping its anti-bot rate limiter.

    Yahoo blocks by client/IP once requests arrive too quickly, so this is a single
    process-wide limiter shared by every ticker fetch rather than one per instance.
    """

    def __init__(self, min_interval_seconds: float) -> None:
        self._min_interval = min_interval_seconds
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call = time.monotonic()


_rate_limiter = _RateLimiter(get_settings().yahoo_min_request_interval_seconds)


def _is_retryable_error(exc: Exception) -> bool:
    message = str(exc)
    return "429" in message or "Too Many Requests" in message or "Expecting value" in message


def _call_with_retry(func: Callable[[], T], ticker: str) -> T:
    settings = get_settings()
    last_exc: Exception | None = None
    for attempt in range(settings.yahoo_max_retries + 1):
        _rate_limiter.wait()
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= settings.yahoo_max_retries or not _is_retryable_error(exc):
                raise
            backoff = settings.yahoo_retry_backoff_seconds
            delay = backoff[min(attempt, len(backoff) - 1)] + random.uniform(0, 1.0)
            logger.warning(
                "rate-limited fetching %s, retrying in %.1fs (attempt %d/%d)",
                ticker,
                delay,
                attempt + 1,
                settings.yahoo_max_retries,
            )
            time.sleep(delay)
    raise last_exc  # pragma: no cover


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

    def get_price_history(self, ticker: str, period: str | None = None) -> pd.DataFrame: ...


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

    def get_price_history(self, ticker: str, period: str | None = None) -> pd.DataFrame:
        settings = get_settings()
        resolved_period = period or settings.history_period
        cache_key = f"{ticker}:{resolved_period}"
        return self._history_cache.get_or_set(cache_key, lambda: self._fetch_history(ticker, resolved_period))

    def _fetch_quote(self, ticker: str) -> QuoteData:
        def fetch() -> dict:
            return yf.Ticker(ticker).info or {}

        try:
            info = _call_with_retry(fetch, ticker)
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
        history = self._fetch_history(ticker, get_settings().history_period)
        if history is None or history.empty:
            return None
        return float(history["Close"].iloc[-1])

    def _fetch_fundamentals(self, ticker: str) -> FundamentalsData:
        def fetch_balance_sheet() -> pd.DataFrame:
            return yf.Ticker(ticker).balance_sheet

        def fetch_income_stmt() -> pd.DataFrame:
            return yf.Ticker(ticker).income_stmt

        try:
            balance_sheet = _call_with_retry(fetch_balance_sheet, ticker)
            income_stmt = _call_with_retry(fetch_income_stmt, ticker)
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

    def _fetch_history(self, ticker: str, period: str) -> pd.DataFrame:
        settings = get_settings()

        def fetch() -> pd.DataFrame:
            return yf.Ticker(ticker).history(
                period=period, interval=settings.history_interval, auto_adjust=True
            )

        try:
            history = _call_with_retry(fetch, ticker)
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
