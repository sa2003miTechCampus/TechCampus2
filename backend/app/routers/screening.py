from fastapi import APIRouter, HTTPException

from ..data_provider import DataUnavailableError, get_data_provider
from ..schemas import ShariahComplianceReport
from ..shariah_screening import build_compliance_report

router = APIRouter(prefix="/api/screening", tags=["screening"])


@router.get("/{ticker}", response_model=ShariahComplianceReport)
def get_screening_report(ticker: str) -> ShariahComplianceReport:
    ticker = ticker.strip().upper()
    provider = get_data_provider()
    try:
        quote = provider.get_quote(ticker)
        fundamentals = provider.get_fundamentals(ticker)
    except DataUnavailableError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error_ar": f"تعذّر العثور على بيانات كافية للسهم {exc.ticker}. تأكد من صحة الرمز.",
                "error_en": f"Could not find sufficient data for ticker {exc.ticker}: {exc.reason}",
            },
        ) from exc
    return build_compliance_report(ticker, quote, fundamentals)
