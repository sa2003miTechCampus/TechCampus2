from fastapi import APIRouter, HTTPException, Query

from ..data_provider import DataUnavailableError, get_data_provider
from ..recommendation_engine import analyze_stock
from ..schemas import PricePoint, StockAnalysis

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


def _not_found(exc: DataUnavailableError) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "error_ar": f"تعذّر العثور على بيانات كافية للسهم {exc.ticker}. تأكد من صحة الرمز.",
            "error_en": f"Could not find sufficient data for ticker {exc.ticker}: {exc.reason}",
        },
    )


@router.get("/{ticker}/history", response_model=list[PricePoint])
def get_stock_history(ticker: str, days: int = Query(default=180, ge=5, le=1000)) -> list[PricePoint]:
    ticker = ticker.strip().upper()
    provider = get_data_provider()
    try:
        history = provider.get_price_history(ticker)
    except DataUnavailableError as exc:
        raise _not_found(exc) from exc
    tail = history.tail(days)
    return [
        PricePoint(date=index.strftime("%Y-%m-%d"), close=float(row["Close"]))
        for index, row in tail.iterrows()
    ]


@router.get("/{ticker}", response_model=StockAnalysis)
def get_stock_analysis(ticker: str) -> StockAnalysis:
    provider = get_data_provider()
    try:
        return analyze_stock(ticker, provider)
    except DataUnavailableError as exc:
        raise _not_found(exc) from exc
