from enum import Enum

from pydantic import BaseModel, Field


class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    NEEDS_REVIEW = "needs_review"


class RecommendationLabel(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class RatioCheck(BaseModel):
    name_ar: str
    name_en: str
    value: float | None
    threshold: float
    passed: bool | None
    description_ar: str


class BusinessScreenResult(BaseModel):
    passed: bool
    matched_exclusions: list[str] = Field(default_factory=list)
    sector: str | None = None
    industry: str | None = None


class FinancialScreenResult(BaseModel):
    debt_to_market_cap: RatioCheck
    cash_and_securities_to_market_cap: RatioCheck
    receivables_to_market_cap: RatioCheck
    impure_income_to_revenue: RatioCheck
    passed: bool
    data_complete: bool


class ShariahComplianceReport(BaseModel):
    ticker: str
    status: ComplianceStatus
    business_screen: BusinessScreenResult
    financial_screen: FinancialScreenResult
    compliance_headroom_score: float
    notes: list[str] = Field(default_factory=list)


class TechnicalIndicators(BaseModel):
    last_price: float
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    ema_12: float | None
    ema_26: float | None
    rsi_14: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    bollinger_upper: float | None
    bollinger_lower: float | None
    bollinger_mid: float | None
    week52_high: float | None
    week52_low: float | None
    volume_trend_pct: float | None


class FundamentalMetrics(BaseModel):
    trailing_pe: float | None
    forward_pe: float | None
    profit_margin: float | None
    revenue_growth: float | None
    market_cap: float | None


class ScoreBreakdown(BaseModel):
    technical_score: float
    fundamental_score: float
    composite_score: float
    technical_weight: float
    fundamental_weight: float


class Recommendation(BaseModel):
    label: RecommendationLabel
    label_ar: str
    score: ScoreBreakdown
    rationale_ar: list[str]
    rationale_en: list[str]


class StockQuote(BaseModel):
    ticker: str
    name: str
    sector: str | None
    industry: str | None
    currency: str
    price: float
    previous_close: float | None
    change_pct: float | None
    market_cap: float | None


class StockAnalysis(BaseModel):
    quote: StockQuote
    compliance: ShariahComplianceReport
    technicals: TechnicalIndicators
    fundamentals: FundamentalMetrics
    recommendation: Recommendation
    disclaimer_ar: str


class DailyPick(BaseModel):
    ticker: str
    name: str
    sector: str | None
    price: float
    change_pct: float | None
    recommendation: RecommendationLabel
    recommendation_ar: str
    composite_score: float
    compliance_status: ComplianceStatus


class DailyRecommendations(BaseModel):
    generated_at: str
    universe_size: int
    compliant_count: int
    picks: list[DailyPick]


class PricePoint(BaseModel):
    date: str
    close: float


class BacktestTrade(BaseModel):
    entry_date: str
    exit_date: str | None
    entry_price: float
    exit_price: float
    return_pct: float
    hold_days: int
    still_open: bool


class EquityPoint(BaseModel):
    date: str
    value: float


class BacktestResult(BaseModel):
    ticker: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    num_trades: int
    win_rate_pct: float | None
    buy_and_hold_return_pct: float
    trades: list[BacktestTrade]
    equity_curve: list[EquityPoint]
    methodology_note_ar: str


class UniverseBacktestEntry(BaseModel):
    ticker: str
    total_return_pct: float
    buy_and_hold_return_pct: float
    num_trades: int
    win_rate_pct: float | None
    beat_buy_and_hold: bool


class UniverseBacktestSummary(BaseModel):
    tested_count: int
    failed_count: int
    average_strategy_return_pct: float
    average_buy_and_hold_return_pct: float
    pct_beating_buy_and_hold: float
    results: list[UniverseBacktestEntry]
    methodology_note_ar: str


class ErrorResponse(BaseModel):
    error_ar: str
    error_en: str
