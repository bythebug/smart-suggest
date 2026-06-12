import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from analysis import aggregate_by_time, calculate_metrics_by_variant, get_statistical_analysis
from ab_testing.manager import assign_variant, create_ab_test
from ab_testing.logger import log_click, log_engagement_time, log_impression, log_purchase
from metrics import (
    avg_engagement_time,
    avg_items_per_user,
    conversion_rate,
    ctr,
    diversity_score,
    z_test_proportions,
)
from models import Base, Item, User, Variant


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    session.add_all([User(username=f"user{i}") for i in range(1, 11)])
    session.add_all(
        [
            Item(name="Laptop", category="electronics"),
            Item(name="Phone", category="electronics"),
            Item(name="Book", category="books"),
        ]
    )
    session.commit()
    yield session
    session.close()


@pytest.fixture
def test_with_events(db):
    """A/B test seeded with known event counts for deterministic assertions."""
    test = create_ab_test(db, "kpi_test", "v1", "v2")

    # Assign users 1–5 to A, users 6–10 to B (override computed variant for test clarity)
    from models import ABTestAssignment
    for uid in range(1, 6):
        db.add(ABTestAssignment(test_id=test.id, user_id=uid, variant=Variant.A))
    for uid in range(6, 11):
        db.add(ABTestAssignment(test_id=test.id, user_id=uid, variant=Variant.B))
    db.commit()

    # Variant A: 10 impressions, 2 clicks, 1 purchase
    for uid in range(1, 6):
        log_impression(db, uid, 1, test.id, Variant.A)
        log_impression(db, uid, 2, test.id, Variant.A)
    log_click(db, 1, 1, test.id, Variant.A)
    log_click(db, 2, 2, test.id, Variant.A)
    log_purchase(db, 1, 1, test.id, Variant.A)

    # Variant B: 10 impressions, 4 clicks, 3 purchases (better performing)
    for uid in range(6, 11):
        log_impression(db, uid, 1, test.id, Variant.B)
        log_impression(db, uid, 2, test.id, Variant.B)
    log_click(db, 6, 1, test.id, Variant.B)
    log_click(db, 7, 1, test.id, Variant.B)
    log_click(db, 8, 2, test.id, Variant.B)
    log_click(db, 9, 2, test.id, Variant.B)
    log_purchase(db, 6, 1, test.id, Variant.B)
    log_purchase(db, 7, 1, test.id, Variant.B)
    log_purchase(db, 8, 2, test.id, Variant.B)

    # Engagement time (no test_id on the event itself)
    for uid in range(1, 6):
        log_engagement_time(db, uid, 1, time_seconds=30.0)
    for uid in range(6, 11):
        log_engagement_time(db, uid, 1, time_seconds=50.0)

    return test


# ---------------------------------------------------------------------------
# test_ctr_calculation
# ---------------------------------------------------------------------------


class TestCTR:
    def test_basic(self):
        assert ctr(100, 10) == pytest.approx(0.1)

    def test_zero_impressions_returns_zero(self):
        assert ctr(0, 0) == pytest.approx(0.0)

    def test_zero_clicks_returns_zero(self):
        assert ctr(200, 0) == pytest.approx(0.0)

    def test_perfect_ctr(self):
        assert ctr(50, 50) == pytest.approx(1.0)

    def test_fractional_result(self):
        assert ctr(3, 1) == pytest.approx(1 / 3)

    def test_more_clicks_than_impressions_allowed(self):
        # Edge case: duplicate-click bugs can produce this; function should not crash.
        assert ctr(10, 15) == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# test_conversion_rate
# ---------------------------------------------------------------------------


class TestConversionRate:
    def test_basic(self):
        assert conversion_rate(100, 5) == pytest.approx(0.05)

    def test_zero_exposed_returns_zero(self):
        assert conversion_rate(0, 0) == pytest.approx(0.0)

    def test_full_conversion(self):
        assert conversion_rate(10, 10) == pytest.approx(1.0)

    def test_fractional_result(self):
        assert conversion_rate(3, 1) == pytest.approx(1 / 3)


class TestAvgEngagementTime:
    def test_basic(self):
        assert avg_engagement_time([10.0, 20.0, 30.0]) == pytest.approx(20.0)

    def test_empty_returns_zero(self):
        assert avg_engagement_time([]) == pytest.approx(0.0)

    def test_single_value(self):
        assert avg_engagement_time([42.5]) == pytest.approx(42.5)

    def test_all_same(self):
        assert avg_engagement_time([5.0, 5.0, 5.0]) == pytest.approx(5.0)


class TestDiversityScore:
    def test_all_unique_returns_one(self):
        assert diversity_score([1, 2, 3, 4, 5]) == pytest.approx(1.0)

    def test_all_same_returns_low_score(self):
        assert diversity_score([1, 1, 1, 1]) == pytest.approx(0.25)

    def test_empty_returns_zero(self):
        assert diversity_score([]) == pytest.approx(0.0)

    def test_partial_diversity(self):
        # [1,2,1,2] → 2 unique / 4 total = 0.5
        assert diversity_score([1, 2, 1, 2]) == pytest.approx(0.5)

    def test_single_item(self):
        assert diversity_score([7]) == pytest.approx(1.0)


class TestAvgItemsPerUser:
    def test_basic(self):
        # User 1: {1,2,3} → 3 unique; User 2: {1,2} → 2 unique; avg = 2.5
        assert avg_items_per_user({1: [1, 2, 3], 2: [1, 1, 2]}) == pytest.approx(2.5)

    def test_empty_returns_zero(self):
        assert avg_items_per_user({}) == pytest.approx(0.0)

    def test_single_user(self):
        assert avg_items_per_user({1: [1, 2, 3, 3]}) == pytest.approx(3.0)

    def test_duplicate_items_deduped(self):
        # User sees same item 10 times → counts as 1 unique
        assert avg_items_per_user({1: [5, 5, 5, 5, 5]}) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# test_metric_aggregation (DB-backed)
# ---------------------------------------------------------------------------


class TestMetricAggregation:
    def test_calculate_metrics_returns_both_variants(self, test_with_events, db):
        result = calculate_metrics_by_variant(db, test_with_events.id)
        assert "A" in result["variants"]
        assert "B" in result["variants"]

    def test_impression_counts_match_seeded_data(self, test_with_events, db):
        result = calculate_metrics_by_variant(db, test_with_events.id)
        assert result["variants"]["A"]["impressions"] == 10
        assert result["variants"]["B"]["impressions"] == 10

    def test_click_counts_match_seeded_data(self, test_with_events, db):
        result = calculate_metrics_by_variant(db, test_with_events.id)
        assert result["variants"]["A"]["clicks"] == 2
        assert result["variants"]["B"]["clicks"] == 4

    def test_ctr_calculated_correctly(self, test_with_events, db):
        result = calculate_metrics_by_variant(db, test_with_events.id)
        assert result["variants"]["A"]["ctr"] == pytest.approx(0.2)   # 2/10
        assert result["variants"]["B"]["ctr"] == pytest.approx(0.4)   # 4/10

    def test_conversion_rate_calculated_correctly(self, test_with_events, db):
        result = calculate_metrics_by_variant(db, test_with_events.id)
        assert result["variants"]["A"]["conversion_rate"] == pytest.approx(1 / 5)   # 1/5 users
        assert result["variants"]["B"]["conversion_rate"] == pytest.approx(3 / 5)   # 3/5 users

    def test_variant_b_outperforms_a(self, test_with_events, db):
        result = calculate_metrics_by_variant(db, test_with_events.id)
        assert result["variants"]["B"]["ctr"] > result["variants"]["A"]["ctr"]
        assert result["variants"]["B"]["conversion_rate"] > result["variants"]["A"]["conversion_rate"]

    def test_lift_is_positive_when_b_better(self, test_with_events, db):
        result = calculate_metrics_by_variant(db, test_with_events.id)
        assert result["lift"]["ctr_absolute"] > 0
        assert result["lift"]["conversion_rate_absolute"] > 0

    def test_avg_engagement_time_attributed_by_variant(self, test_with_events, db):
        result = calculate_metrics_by_variant(db, test_with_events.id)
        assert result["variants"]["A"]["avg_engagement_time_s"] == pytest.approx(30.0)
        assert result["variants"]["B"]["avg_engagement_time_s"] == pytest.approx(50.0)

    def test_aggregate_by_time_returns_list(self, test_with_events, db):
        result = aggregate_by_time(db, test_with_events.id, period="day")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_aggregate_by_time_each_entry_has_both_variants(self, test_with_events, db):
        result = aggregate_by_time(db, test_with_events.id, period="day")
        for entry in result:
            assert "A" in entry
            assert "B" in entry
            assert "ctr" in entry["A"]
            assert "ctr" in entry["B"]

    def test_aggregate_by_time_invalid_period_raises(self, test_with_events, db):
        with pytest.raises(ValueError, match="period must be"):
            aggregate_by_time(db, test_with_events.id, period="week")

    def test_empty_test_returns_zero_metrics(self, db):
        test = create_ab_test(db, "empty_test")
        result = calculate_metrics_by_variant(db, test.id)
        assert result["variants"]["A"]["impressions"] == 0
        assert result["variants"]["B"]["ctr"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Z-test
# ---------------------------------------------------------------------------


class TestZTestProportions:
    def test_no_effect_z_score_is_zero(self):
        result = z_test_proportions(n_a=1000, p_a=0.1, n_b=1000, p_b=0.1)
        assert result["z_score"] == pytest.approx(0.0)
        assert not result["significant"]

    def test_significant_improvement(self):
        result = z_test_proportions(n_a=10_000, p_a=0.10, n_b=10_000, p_b=0.15)
        assert result["significant"]
        assert result["p_value"] < 0.05

    def test_zero_sample_size_returns_none(self):
        result = z_test_proportions(n_a=0, p_a=0.0, n_b=100, p_b=0.1)
        assert result["z_score"] is None
        assert result["p_value"] is None
        assert not result["significant"]

    def test_equal_zero_proportions_returns_none(self):
        result = z_test_proportions(n_a=100, p_a=0.0, n_b=100, p_b=0.0)
        assert result["z_score"] is None

    def test_b_worse_than_a_gives_negative_z(self):
        result = z_test_proportions(n_a=10_000, p_a=0.2, n_b=10_000, p_b=0.1)
        assert result["z_score"] < 0

    def test_p_value_between_zero_and_one(self):
        result = z_test_proportions(n_a=500, p_a=0.1, n_b=500, p_b=0.12)
        assert 0.0 <= result["p_value"] <= 1.0

    def test_statistical_analysis_endpoint(self, test_with_events, db):
        result = get_statistical_analysis(db, test_with_events.id)
        assert "statistical_tests" in result
        assert "ctr" in result["statistical_tests"]
        assert "conversion_rate" in result["statistical_tests"]
        assert "z_score" in result["statistical_tests"]["ctr"]
