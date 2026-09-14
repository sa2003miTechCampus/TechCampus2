from fastapi import APIRouter, HTTPException, Query

from ..backtesting import InsufficientHistoryError, run_backtest, run_universe_backtest
from ..data_provider import DataUnavailableError, get_data_provider
from ..schemas import BacktestResult, UniverseBacktestSummary

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.get("/universe", response_model=UniverseBacktestSummary)
def get_universe_backtest(limit: int = Query(default=20, ge=1, le=50)) -> UniverseBacktestSummary:
    provider = get_data_provider()
    return run_universe_backtest(provider, limit=limit)


@router.get("/{ticker}", response_model=BacktestResult)
def get_ticker_backtest(
    ticker: str, initial_capital: float = Query(default=10_000.0, gt=0)
) -> BacktestResult:
    provider = get_data_provider()
    try:
        return run_backtest(ticker, provider, initial_capital=initial_capital)
    except DataUnavailableError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error_ar": f"تعذّر العثور على بيانات كافية للسهم {exc.ticker}. تأكد من صحة الرمز.",
                "error_en": f"Could not find sufficient data for ticker {exc.ticker}: {exc.reason}",
            },
        ) from exc
    except InsufficientHistoryError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_ar": (
                    f"بيانات {exc.ticker} التاريخية غير كافية لإجراء اختبار خلفي موثوق "
                    f"({exc.available_days} يوم تداول متاح، يلزم {exc.required_days} على الأقل)."
                ),
                "error_en": str(exc),
            },
        ) from exc
