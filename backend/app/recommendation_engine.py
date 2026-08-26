from __future__ import annotations

from .config import get_settings
from .data_provider import DataUnavailableError, MarketDataProvider
from .schemas import (
    ComplianceStatus,
    FundamentalMetrics,
    Recommendation,
    RecommendationLabel,
    ScoreBreakdown,
    ShariahComplianceReport,
    StockAnalysis,
    StockQuote,
    TechnicalIndicators,
)
from .scoring import build_score_breakdown
from .shariah_screening import build_compliance_report
from .technical_analysis import compute_technical_indicators

DISCLAIMER_AR = (
    "هذا التحليل والتوصية نتاج نموذج آلي لأغراض تعليمية وبحثية فقط، ولا يشكل استشارة "
    "مالية أو فتوى شرعية. الأداء السابق لا يضمن نتائج مستقبلية، ويُنصح بمراجعة مستشار "
    "مالي مرخّص وهيئة شرعية معتمدة قبل اتخاذ أي قرار استثماري."
)

_LABEL_AR = {
    RecommendationLabel.STRONG_BUY: "شراء قوي",
    RecommendationLabel.BUY: "شراء",
    RecommendationLabel.HOLD: "احتفاظ",
    RecommendationLabel.SELL: "بيع",
    RecommendationLabel.STRONG_SELL: "بيع قوي",
}


def label_from_score(score: float) -> RecommendationLabel:
    settings = get_settings()
    if score >= settings.strong_buy_threshold:
        return RecommendationLabel.STRONG_BUY
    if score >= settings.buy_threshold:
        return RecommendationLabel.BUY
    if score <= settings.strong_sell_threshold:
        return RecommendationLabel.STRONG_SELL
    if score <= settings.sell_threshold:
        return RecommendationLabel.SELL
    return RecommendationLabel.HOLD


def _build_rationale(
    indicators: TechnicalIndicators,
    fundamentals: FundamentalMetrics,
    compliance: ShariahComplianceReport,
) -> tuple[list[str], list[str]]:
    rationale_ar: list[str] = []
    rationale_en: list[str] = []

    if indicators.sma_50 is not None and indicators.sma_200 is not None:
        if indicators.last_price > indicators.sma_50 > indicators.sma_200:
            rationale_ar.append("الاتجاه العام صاعد: السعر أعلى من المتوسطين المتحركين 50 و200 يوم.")
            rationale_en.append("Uptrend: price is above both the 50-day and 200-day moving averages.")
        elif indicators.last_price < indicators.sma_50 < indicators.sma_200:
            rationale_ar.append("الاتجاه العام هابط: السعر أدنى من المتوسطين المتحركين 50 و200 يوم.")
            rationale_en.append("Downtrend: price is below both the 50-day and 200-day moving averages.")

    if indicators.rsi_14 is not None:
        if indicators.rsi_14 <= 30:
            rationale_ar.append(f"تشبع بيعي وفق مؤشر RSI ({indicators.rsi_14:.1f})، احتمال ارتداد صاعد.")
            rationale_en.append(f"RSI ({indicators.rsi_14:.1f}) indicates oversold conditions.")
        elif indicators.rsi_14 >= 70:
            rationale_ar.append(f"تشبع شرائي وفق مؤشر RSI ({indicators.rsi_14:.1f})، احتمال تصحيح هابط.")
            rationale_en.append(f"RSI ({indicators.rsi_14:.1f}) indicates overbought conditions.")

    if indicators.macd_histogram is not None:
        if indicators.macd_histogram > 0:
            rationale_ar.append("زخم إيجابي وفق مؤشر MACD.")
            rationale_en.append("MACD histogram is positive, signalling bullish momentum.")
        elif indicators.macd_histogram < 0:
            rationale_ar.append("زخم سلبي وفق مؤشر MACD.")
            rationale_en.append("MACD histogram is negative, signalling bearish momentum.")

    if fundamentals.revenue_growth is not None:
        pct = fundamentals.revenue_growth * 100
        if pct > 10:
            rationale_ar.append(f"نمو قوي في الإيرادات ({pct:.1f}%).")
            rationale_en.append(f"Strong revenue growth ({pct:.1f}%).")
        elif pct < 0:
            rationale_ar.append(f"تراجع في الإيرادات ({pct:.1f}%).")
            rationale_en.append(f"Revenue is declining ({pct:.1f}%).")

    if fundamentals.trailing_pe is not None:
        if fundamentals.trailing_pe > 40:
            rationale_ar.append(f"التقييم مرتفع نسبياً (مكرر ربحية {fundamentals.trailing_pe:.1f}).")
            rationale_en.append(f"Valuation looks stretched (P/E {fundamentals.trailing_pe:.1f}).")
        elif 0 < fundamentals.trailing_pe < 15:
            rationale_ar.append(f"التقييم معقول نسبياً (مكرر ربحية {fundamentals.trailing_pe:.1f}).")
            rationale_en.append(f"Valuation looks reasonable (P/E {fundamentals.trailing_pe:.1f}).")

    if compliance.status == ComplianceStatus.COMPLIANT:
        rationale_ar.append("السهم اجتاز الفحص الشرعي الآلي (النشاط التجاري والنسب المالية).")
        rationale_en.append("The stock passed the automated Sharia screen (business + financial ratios).")
    elif compliance.status == ComplianceStatus.NON_COMPLIANT:
        rationale_ar.append("تنبيه: السهم لم يجتز الفحص الشرعي الآلي، وغير مناسب لمحفظة حلال.")
        rationale_en.append("Warning: the stock failed the automated Sharia screen and is not halal-eligible.")
    else:
        rationale_ar.append("تنبيه: تعذّر إكمال الفحص الشرعي بسبب نقص بيانات مالية.")
        rationale_en.append("Warning: the Sharia screen is inconclusive due to missing financial data.")

    return rationale_ar, rationale_en


def _build_recommendation(
    score: ScoreBreakdown,
    indicators: TechnicalIndicators,
    fundamentals: FundamentalMetrics,
    compliance: ShariahComplianceReport,
) -> Recommendation:
    label = label_from_score(score.composite_score)
    rationale_ar, rationale_en = _build_rationale(indicators, fundamentals, compliance)
    return Recommendation(
        label=label,
        label_ar=_LABEL_AR[label],
        score=score,
        rationale_ar=rationale_ar,
        rationale_en=rationale_en,
    )


def analyze_stock(ticker: str, provider: MarketDataProvider) -> StockAnalysis:
    ticker = ticker.strip().upper()
    if not ticker:
        raise DataUnavailableError(ticker, "empty ticker")

    quote = provider.get_quote(ticker)
    fundamentals_data = provider.get_fundamentals(ticker)
    history = provider.get_price_history(ticker)

    indicators = compute_technical_indicators(history)
    fundamentals = FundamentalMetrics(
        trailing_pe=quote.trailing_pe,
        forward_pe=quote.forward_pe,
        profit_margin=quote.profit_margin,
        revenue_growth=quote.revenue_growth,
        market_cap=quote.market_cap,
    )
    compliance = build_compliance_report(ticker, quote, fundamentals_data)
    score = build_score_breakdown(indicators, fundamentals)
    recommendation = _build_recommendation(score, indicators, fundamentals, compliance)

    change_pct = None
    if quote.previous_close:
        change_pct = (quote.price - quote.previous_close) / quote.previous_close * 100

    stock_quote = StockQuote(
        ticker=ticker,
        name=quote.name,
        sector=quote.sector,
        industry=quote.industry,
        currency=quote.currency,
        price=quote.price,
        previous_close=quote.previous_close,
        change_pct=change_pct,
        market_cap=quote.market_cap,
    )

    return StockAnalysis(
        quote=stock_quote,
        compliance=compliance,
        technicals=indicators,
        fundamentals=fundamentals,
        recommendation=recommendation,
        disclaimer_ar=DISCLAIMER_AR,
    )
