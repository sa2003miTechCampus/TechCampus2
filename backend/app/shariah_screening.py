"""AAOIFI / Dow Jones Islamic Market-style Sharia compliance screening.

Two-stage screen, consistent with the methodology used by major Islamic
indices (DJIM, S&P Shariah, MSCI Islamic):

1. Business (qualitative) screen - excludes companies whose primary
   activity is conventional banking/finance, insurance, alcohol,
   gambling, tobacco, pork, adult entertainment or weapons manufacturing.

2. Financial (quantitative) screen - three balance-sheet ratios must each
   stay below 33% of market capitalisation (interest-bearing debt; cash
   and interest-bearing securities; receivables), and non-compliant
   ("impure") income must stay below 5% of total revenue.

This is an automated, data-driven screen for informational and research
purposes. It is not a fatwa and does not replace guidance from a
qualified Sharia scholar or board - see the disclaimer surfaced with
every report.
"""

from __future__ import annotations

from .config import get_settings
from .data_provider import FundamentalsData, QuoteData
from .schemas import (
    BusinessScreenResult,
    ComplianceStatus,
    FinancialScreenResult,
    RatioCheck,
    ShariahComplianceReport,
)

EXCLUDED_KEYWORDS: dict[str, str] = {
    "bank": "أعمال مصرفية تقليدية قائمة على الفائدة",
    "insurance": "تأمين تقليدي غير تكافلي",
    "credit services": "خدمات ائتمانية قائمة على الفائدة",
    "capital markets": "أسواق مال / وساطة مالية تقليدية",
    "mortgage": "تمويل عقاري قائم على الفائدة",
    "asset management": "إدارة أصول مالية تقليدية",
    "brewers": "إنتاج مشروبات كحولية",
    "distillers": "إنتاج مشروبات كحولية",
    "wineries": "إنتاج مشروبات كحولية",
    "beverages - alcoholic": "إنتاج مشروبات كحولية",
    "casino": "قمار ومراهنات",
    "gambling": "قمار ومراهنات",
    "resorts & casinos": "قمار ومراهنات",
    "tobacco": "إنتاج التبغ",
    "adult entertainment": "محتوى للبالغين",
    "pornography": "محتوى للبالغين",
    "pork": "إنتاج لحم الخنزير",
    "weapons": "تصنيع أسلحة",
    "ammunition": "تصنيع ذخائر",
}


def screen_business_activity(quote: QuoteData) -> BusinessScreenResult:
    haystack = f"{quote.sector or ''} {quote.industry or ''}".lower()
    matched = [
        label for keyword, label in EXCLUDED_KEYWORDS.items() if keyword in haystack
    ]
    return BusinessScreenResult(
        passed=len(matched) == 0,
        matched_exclusions=matched,
        sector=quote.sector,
        industry=quote.industry,
    )


def _ratio_check(
    name_ar: str,
    name_en: str,
    numerator: float | None,
    denominator: float | None,
    threshold: float,
    description_ar: str,
) -> RatioCheck:
    if numerator is None or denominator is None or denominator == 0:
        return RatioCheck(
            name_ar=name_ar,
            name_en=name_en,
            value=None,
            threshold=threshold,
            passed=None,
            description_ar=description_ar,
        )
    value = numerator / denominator
    return RatioCheck(
        name_ar=name_ar,
        name_en=name_en,
        value=value,
        threshold=threshold,
        passed=value <= threshold,
        description_ar=description_ar,
    )


def screen_financial_ratios(
    quote: QuoteData, fundamentals: FundamentalsData
) -> FinancialScreenResult:
    settings = get_settings()
    market_cap = quote.market_cap

    debt_check = _ratio_check(
        "الدين إلى القيمة السوقية",
        "Debt / Market Cap",
        fundamentals.total_debt,
        market_cap,
        settings.screening_max_debt_to_market_cap,
        "إجمالي الدين المُثقل بالفائدة يجب ألا يتجاوز 33% من القيمة السوقية",
    )
    cash_check = _ratio_check(
        "النقد والأوراق المالية إلى القيمة السوقية",
        "Cash & Securities / Market Cap",
        fundamentals.total_cash_and_securities,
        market_cap,
        settings.screening_max_cash_securities_to_market_cap,
        "النقد والأوراق المالية المدرة للفائدة يجب ألا تتجاوز 33% من القيمة السوقية",
    )
    receivables_check = _ratio_check(
        "الذمم المدينة إلى القيمة السوقية",
        "Receivables / Market Cap",
        fundamentals.net_receivables,
        market_cap,
        settings.screening_max_receivables_to_market_cap,
        "الذمم المدينة يجب ألا تتجاوز 33% من القيمة السوقية",
    )
    impure_income_known = fundamentals.impure_income is not None
    impure_income_numerator = (
        abs(fundamentals.impure_income) if impure_income_known else 0.0
    ) if fundamentals.total_revenue is not None else None
    impure_income_check = _ratio_check(
        "الدخل غير النقي إلى الإيرادات",
        "Impure Income / Revenue",
        impure_income_numerator,
        fundamentals.total_revenue,
        settings.screening_max_impure_income_to_revenue,
        "دخل الفوائد وغيره من الدخل غير المتوافق يجب ألا يتجاوز 5% من إجمالي الإيرادات "
        "(يجب تطهير هذه النسبة من الأرباح حتى عند الامتثال)",
    )

    checks = [debt_check, cash_check, receivables_check, impure_income_check]
    data_complete = all(check.value is not None for check in checks)
    passed = all(check.passed for check in checks if check.passed is not None) and data_complete

    return FinancialScreenResult(
        debt_to_market_cap=debt_check,
        cash_and_securities_to_market_cap=cash_check,
        receivables_to_market_cap=receivables_check,
        impure_income_to_revenue=impure_income_check,
        passed=passed,
        data_complete=data_complete,
    )


def _headroom_score(financial_screen: FinancialScreenResult) -> float:
    checks = [
        financial_screen.debt_to_market_cap,
        financial_screen.cash_and_securities_to_market_cap,
        financial_screen.receivables_to_market_cap,
        financial_screen.impure_income_to_revenue,
    ]
    margins = []
    for check in checks:
        if check.value is None or check.threshold == 0:
            continue
        margin = 1.0 - (check.value / check.threshold)
        margins.append(max(0.0, min(1.0, margin)))
    if not margins:
        return 0.0
    return round(sum(margins) / len(margins) * 100, 2)


def build_compliance_report(
    ticker: str, quote: QuoteData, fundamentals: FundamentalsData
) -> ShariahComplianceReport:
    business_screen = screen_business_activity(quote)
    financial_screen = screen_financial_ratios(quote, fundamentals)

    notes: list[str] = []
    if fundamentals.impure_income is None:
        notes.append(
            "لم يتم العثور على بند دخل فوائد منفصل في البيانات المالية المتاحة؛ "
            "تم افتراض أنه صفر عند احتساب نسبة الدخل غير النقي، ويُنصح بالتحقق يدوياً."
        )
    notes += [
        "هذا الفرز آلي ويعتمد على البيانات المالية العامة المتاحة، وهو لأغراض معلوماتية "
        "وبحثية فقط، ولا يُعد فتوى شرعية. يُرجى استشارة هيئة شرعية معتمدة قبل اتخاذ قرار استثماري."
    ]

    if not business_screen.passed:
        status = ComplianceStatus.NON_COMPLIANT
        notes.append(
            "استُبعد السهم بسبب النشاط التجاري: " + "، ".join(business_screen.matched_exclusions)
        )
    elif not financial_screen.data_complete:
        status = ComplianceStatus.NEEDS_REVIEW
        notes.append("بعض البيانات المالية اللازمة لاحتساب النسب الشرعية غير متوفرة حالياً.")
    elif financial_screen.passed:
        status = ComplianceStatus.COMPLIANT
    else:
        status = ComplianceStatus.NON_COMPLIANT
        notes.append("تجاوزت إحدى النسب المالية الحد الشرعي المسموح به (33% أو 5%).")

    headroom = _headroom_score(financial_screen) if business_screen.passed else 0.0

    return ShariahComplianceReport(
        ticker=ticker,
        status=status,
        business_screen=business_screen,
        financial_screen=financial_screen,
        compliance_headroom_score=headroom,
        notes=notes,
    )
