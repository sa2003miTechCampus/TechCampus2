from app.data_provider import FundamentalsData
from app.schemas import ComplianceStatus
from app.shariah_screening import build_compliance_report, screen_business_activity


def test_business_screen_passes_for_technology(compliant_quote):
    result = screen_business_activity(compliant_quote)
    assert result.passed is True
    assert result.matched_exclusions == []


def test_business_screen_excludes_conventional_bank(bank_quote):
    result = screen_business_activity(bank_quote)
    assert result.passed is False
    assert result.matched_exclusions


def test_compliance_report_compliant(compliant_quote, compliant_fundamentals):
    report = build_compliance_report("HALAL", compliant_quote, compliant_fundamentals)
    assert report.status == ComplianceStatus.COMPLIANT
    assert report.financial_screen.passed is True
    assert report.compliance_headroom_score > 0


def test_compliance_report_non_compliant_business(bank_quote, compliant_fundamentals):
    report = build_compliance_report("BANK", bank_quote, compliant_fundamentals)
    assert report.status == ComplianceStatus.NON_COMPLIANT
    assert report.compliance_headroom_score == 0.0


def test_compliance_report_non_compliant_financial_ratio(
    highly_leveraged_quote, highly_leveraged_fundamentals
):
    report = build_compliance_report(
        "DEBTCO", highly_leveraged_quote, highly_leveraged_fundamentals
    )
    assert report.financial_screen.debt_to_market_cap.passed is False
    assert report.status == ComplianceStatus.NON_COMPLIANT


def test_compliance_report_needs_review_on_missing_data(compliant_quote):
    incomplete = FundamentalsData(
        total_debt=None,
        total_cash_and_securities=None,
        net_receivables=None,
        total_revenue=None,
        impure_income=None,
        data_complete=False,
    )
    report = build_compliance_report("HALAL", compliant_quote, incomplete)
    assert report.status == ComplianceStatus.NEEDS_REVIEW


def test_impure_income_missing_is_noted_but_not_fatal(compliant_quote, compliant_fundamentals):
    fundamentals = FundamentalsData(
        total_debt=compliant_fundamentals.total_debt,
        total_cash_and_securities=compliant_fundamentals.total_cash_and_securities,
        net_receivables=compliant_fundamentals.net_receivables,
        total_revenue=compliant_fundamentals.total_revenue,
        impure_income=None,
        data_complete=True,
    )
    report = build_compliance_report("HALAL", compliant_quote, fundamentals)
    assert report.financial_screen.impure_income_to_revenue.value == 0.0
    assert any("دخل فوائد" in note for note in report.notes)
