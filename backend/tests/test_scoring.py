from tests.conftest import make_declining_history, make_trending_history

from app.schemas import FundamentalMetrics
from app.scoring import build_score_breakdown, compute_fundamental_score, compute_technical_score
from app.technical_analysis import compute_technical_indicators


def test_technical_score_positive_for_uptrend():
    indicators = compute_technical_indicators(make_trending_history())
    score = compute_technical_score(indicators)
    assert score > 0


def test_technical_score_negative_for_downtrend():
    indicators = compute_technical_indicators(make_declining_history())
    score = compute_technical_score(indicators)
    assert score < 0


def test_technical_score_bounded():
    indicators = compute_technical_indicators(make_trending_history(daily_drift=5.0))
    score = compute_technical_score(indicators)
    assert -100 <= score <= 100


def test_fundamental_score_rewards_growth_and_margins():
    strong = FundamentalMetrics(
        trailing_pe=18.0, forward_pe=16.0, profit_margin=0.30, revenue_growth=0.25, market_cap=1e11
    )
    weak = FundamentalMetrics(
        trailing_pe=60.0, forward_pe=55.0, profit_margin=-0.05, revenue_growth=-0.10, market_cap=1e9
    )
    assert compute_fundamental_score(strong) > compute_fundamental_score(weak)


def test_fundamental_score_neutral_when_no_data():
    empty = FundamentalMetrics(
        trailing_pe=None, forward_pe=None, profit_margin=None, revenue_growth=None, market_cap=None
    )
    assert compute_fundamental_score(empty) == 0.0


def test_composite_score_blends_technical_and_fundamental():
    indicators = compute_technical_indicators(make_trending_history())
    fundamentals = FundamentalMetrics(
        trailing_pe=18.0, forward_pe=16.0, profit_margin=0.30, revenue_growth=0.25, market_cap=1e11
    )
    breakdown = build_score_breakdown(indicators, fundamentals)
    assert breakdown.composite_score == round(
        breakdown.technical_score * breakdown.technical_weight
        + breakdown.fundamental_score * breakdown.fundamental_weight,
        2,
    )
