import pytest
from tests.conftest import FakeProvider, make_declining_history, make_trending_history

from app.recommendation_engine import label_from_score
from app.schemas import ComplianceStatus, RecommendationLabel


def test_label_from_score_thresholds():
    assert label_from_score(80) == RecommendationLabel.STRONG_BUY
    assert label_from_score(30) == RecommendationLabel.BUY
    assert label_from_score(0) == RecommendationLabel.HOLD
    assert label_from_score(-30) == RecommendationLabel.SELL
    assert label_from_score(-80) == RecommendationLabel.STRONG_SELL


def test_analyze_stock_compliant_uptrend(compliant_quote, compliant_fundamentals):
    from app.recommendation_engine import analyze_stock

    provider = FakeProvider(
        quotes={"HALAL": compliant_quote},
        fundamentals={"HALAL": compliant_fundamentals},
        histories={"HALAL": make_trending_history()},
    )
    analysis = analyze_stock("halal", provider)

    assert analysis.quote.ticker == "HALAL"
    assert analysis.compliance.status == ComplianceStatus.COMPLIANT
    assert analysis.recommendation.label in (
        RecommendationLabel.BUY,
        RecommendationLabel.STRONG_BUY,
        RecommendationLabel.HOLD,
    )
    assert analysis.disclaimer_ar
    assert len(analysis.recommendation.rationale_ar) == len(analysis.recommendation.rationale_en)


def test_analyze_stock_non_compliant_bank(bank_quote, compliant_fundamentals):
    from app.recommendation_engine import analyze_stock

    provider = FakeProvider(
        quotes={"BANK": bank_quote},
        fundamentals={"BANK": compliant_fundamentals},
        histories={"BANK": make_declining_history()},
    )
    analysis = analyze_stock("BANK", provider)
    assert analysis.compliance.status == ComplianceStatus.NON_COMPLIANT


def test_analyze_stock_raises_for_unknown_ticker():
    from app.data_provider import DataUnavailableError
    from app.recommendation_engine import analyze_stock

    provider = FakeProvider()
    with pytest.raises(DataUnavailableError):
        analyze_stock("UNKNOWN", provider)
